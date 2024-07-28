# -*- coding: utf-8 -*-
import pandas as pd
import datetime

from c2matica_py_server.settings import MYSQL_HOST, MYSQL_USERNAME, MYSQL_PASSWORD, MYSQL_DATABASE
from common.sql_util import *
import pymysql
from common.logger import Logger
import re


class Schedule():
    def __init__(self, schedule_date, input_saving=True):

        self.input_saving = input_saving

        self.logger = Logger(__name__).get_logger()
        self.logger.info("Schedule initializing...")

        self.date = datetime.datetime.strptime(schedule_date, "%Y-%m-%d")
        self.strf_date = self.date.strftime("%Y-%m-%d")
        self.weekday = self.__get_weekday()

        self.__dept_seq_to_room_id = self.__get_dept_seq_to_room_id()
        self.doctor_workload = {}
        self.rooms = {}
        self.rooms_info_dict = self.__get_room_info()

        self.logger.info("Schedule initialized")

    def __get_weekday(self):
        chinese2num = {'星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, '星期五': 5, '星期六': 6, '星期日': 7}

        if self.date.weekday() in [0, 1, 2, 3, 4]:
            self.logger.info("当前日期是工作日")
            return self.date.weekday() + 1
        else:
            self.logger.info("当前日期是周末，需要获取映射")
            sql = """
                        select 
                               *
                        from mapping_date od
                        where od.date = '{}'
                    """.format(self.strf_date)
            temp_data = query_all_dict(sql)
            mapping_date = pd.DataFrame(temp_data)
            strWeekday = mapping_date["week"][0]
            return chinese2num[strWeekday]

    def __get_dept_seq_to_room_id(self):
        sql = """
               SELECT 
                    ss.department AS dept, 
                    ss.surgery_room_sequence AS seq_alphabet, 
                    ri.id AS room_id, 
                    CASE
                        WHEN ss.remarks LIKE '%优先排%' THEN 0
                        WHEN ss.remarks LIKE '%往后排%' THEN 2000
                        ELSE 1000
                    END AS weight
                FROM 
                    surgery_schedule ss
                JOIN 
                    operating_room_info ri 
                ON 
                    ss.surgery_department LIKE CONCAT('%', ri.operating_department, '%') 
                    AND 
                    CAST(ss.surgery_room_name AS CHAR) = CAST(ri.real_name AS UNSIGNED)
                WHERE 
                    ss.week = '{}'
            """.format(self.weekday)

        df = pd.DataFrame(query_all_dict(sql))

        # dealing with 、problem
        extended = []
        for row in df.itertuples():
            dept = row.dept
            seq_alphabet = row.seq_alphabet
            room_id = row.room_id
            weight = row.weight

            # the number of 、 in seq_alphabet and dept should be the same and less than 1
            assert seq_alphabet.count('、') == dept.count('、') and seq_alphabet.count('、') <= 1

            if '、' in seq_alphabet:
                dept_1, dept_2 = dept.split('、')
                seq_1, seq_2 = seq_alphabet.split('、')
                extended.append([dept_1, seq_1, room_id, weight])
                extended.append([dept_2, seq_2, room_id, weight])
            else:
                extended.append([dept, seq_alphabet, room_id, weight])

        df = pd.DataFrame(extended, columns=['dept', 'seq_alphabet', 'room_id', 'weight'])
        # set the dtype of columns
        df = df.astype({'dept': str, 'seq_alphabet': str, 'room_id': int, 'weight': int})
        self.logger.info("当前星期{},当前星期的手术室分配为:\n{}".format(self.weekday, df))
        return df

    def __get_room_id_and_weight(self, dept, seq_alphabet):
        """
        Based on the department and the sequence alphabet, and self.weekday, return the room id.
        :param dept:
        :param seq_alphabet:
        :return:
        """
        # using re to drop the digits of dept
        fuzzy_dept = re.sub(r"\d+", "", dept)

        # select the where self.__dept_seq_to_room_id["dept"] contains fuzzy_dept
        seq_df = self.__dept_seq_to_room_id.loc[self.__dept_seq_to_room_id["dept"].str.contains(fuzzy_dept)]

        if seq_df.__len__() == 0:
            self.logger.info("当前科室{}当日没有对应的手术室".format(dept))
            return None, None

        seq_df = seq_df.loc[seq_df["seq_alphabet"] == seq_alphabet]
        if seq_df.__len__() == 0:
            self.logger.info("当前科室{}{}当日没有对应的手术室".format(dept, seq_alphabet))
            return None, None
        else:
            room_id = seq_df["room_id"].values[0]
            weight = seq_df["weight"].values[0]
            self.logger.info("当前科室{}{}当日对应的手术室为{}".format(dept, seq_alphabet, room_id))
            return room_id, weight

    def __check_doctor_overwork(self, doctor, max_workload=13.0):
        """
        Get the doctor workload of the current day.
        :return:
        """

        if doctor not in self.doctor_workload:
            self.doctor_workload[doctor] = 0.0
        return self.doctor_workload[doctor] > max_workload

    def __get_room_workload(self, room_id, interval=0.5):
        """
        Get the room workload of the current day.
        :return:
        """
        total_duration = 0.0
        for application in self.rooms[room_id]:
            total_duration += application['duration'] + interval
        return total_duration

    def __check_room_overwork(self, room_id, max_workload=13.0, interval=0.5):
        """
        Get the room workload of the current day, noted the last application must end before 8:00 + 13:00 = 21:00
        :return:
        """
        return self.__get_room_workload(room_id, interval) - interval > max_workload

    def __get_unarranged_applications(self):
        """
        Get the applications that have not been arranged.
        :return:
        """
        sql = """
            select 
                  application_number as 'id',
                  surgeon as 'doctor',
                  apply_department as 'dept',
                  estimated_duration_operation as 'duration',
                  table_sequence as 'seq'
            from 
                surgicalapplicationinfo_python
            where
                pseudo_operation_data like '{}%' AND !arrange_operating_room_number
                               """.format(self.strf_date)

        waiting_list = []
        for row in query_all_dict(sql):
            application = {'id': row['id'],
                           'doctor': row['doctor'],
                           'dept': row['dept'],
                           'duration': round(float(row['duration'])),  # 向上取整
                           # 分解手术序列，A1->A,1
                           'seq_alphabet': row['seq'][0],
                           'seq_number': int(row['seq'][1:])
                           }
            waiting_list.append(application)
        return waiting_list

    def run(self):
        self.logger.info("Schedule running...")

        self.logger.info("获取waiting list...")
        waiting_list = self.__get_unarranged_applications()
        self.logger.info("waiting list获取成功")
        self.logger.info("waiting list长度为{}".format(len(waiting_list)))

        for application in waiting_list:
            self.logger.info("#" * 40)
            self.logger.info("#" * 40)
            self.logger.info("#" * 40)

            self.logger.info("当前申请{}".format(application))

            if self.__check_doctor_overwork(application['doctor']):
                self.logger.info("医生{}已经超过工作量".format(application['doctor']))
                self.logger.info("跳过当前申请")
                continue

            room_id, init_weight = self.__get_room_id_and_weight(application['dept'], application['seq_alphabet'])
            if not room_id:
                self.logger.info("当前申请没有对应的手术室")
                self.logger.info("跳过当前申请")
                continue

            weight = init_weight + 100 * (ord(application['seq_alphabet']) - ord('A')) + application['seq_number']
            operating_department = self.rooms_info_dict[room_id]["operating_department"]
            real_name = self.rooms_info_dict[room_id]["real_name"]

            self.logger.info("当前申请对应的手术室为{}({},{})".format(room_id, operating_department, real_name))
            self.logger.info("当前申请的权重为{}".format(weight))
            application["weight"] = weight

            self.logger.info("加入到手术室中")
            if room_id not in self.rooms:
                self.rooms[room_id] = []
            self.rooms[room_id].append(application)

            self.logger.info("更新医生工作量")
            self.doctor_workload[application['doctor']] += application['duration']
            self.logger.info("当前医生{}的工作量为{}".format(application['doctor'],
                                                             self.doctor_workload[application['doctor']]))

            self.logger.info("基于权重排序")
            self.rooms[room_id].sort(key=lambda x: x['weight'])

            self.logger.info("当前手术室的申请列表长度为{}".format(len(self.rooms[room_id])))
            self.logger.info("当前手术室的占用时长为{}".format(self.__get_room_workload(room_id)))

            while self.__check_room_overwork(room_id):
                self.logger.info("手术室{}已经超过工作量".format(room_id))
                self.logger.info("删除最后一个申请")
                dropped_application = self.rooms[room_id].pop()
                self.logger.info("删除的申请为{}".format(dropped_application))
                self.logger.info("更新医生工作量")
                self.doctor_workload[dropped_application['doctor']] -= dropped_application['duration']
                self.logger.info("当前医生{}的工作量为{}".format(dropped_application['doctor'],
                                                                 self.doctor_workload[dropped_application['doctor']]))

        self.logger.info("回写数据库")
        for room_id, applications in self.rooms.items():
            operating_department = self.rooms_info_dict[room_id]["operating_department"]  # 手术部
            real_name = self.rooms_info_dict[room_id]["real_name"]  # 真实名称
            for application in applications:
                sql = """
                update 
                    surgicalapplicationinfo_python
                set 
                    has_arranged = '是',
                    arrange_operating_number = '{}',
                    arrange_operating_room = '{}',
                    arrange_operating_room_number = '{}',
                    second_round_scheduling_weight = '{}'
                where 
                    application_number = '{}' and pseudo_operation_data like '{}%'
                                """.format(operating_department,
                                           real_name,
                                           room_id,
                                           application["weight"],
                                           application["id"],
                                           self.strf_date)

                conn = pymysql.connect(host=MYSQL_HOST,
                                       user=MYSQL_USERNAME,
                                       password=MYSQL_PASSWORD,
                                       database=MYSQL_DATABASE, charset="utf8")
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                cursor.close()
                conn.close()
        self.logger.info("数据库回写成功")
        self.logger.info("Schedule runned")

    def __get_room_info(self):
        """
        Get the room info from the database.
        and return a dict with room_id as key and room info as value.
        room info is a dict with op_dept and r_name as key.
        :return:
        """
        result = {}
        sql = """
            select 
                  id,
                  operating_department,
                  real_name
            from 
                operating_room_info
        """
        for row in query_all_dict(sql):
            result[row["id"]] = {"operating_department": row["operating_department"],
                                 "real_name": row["real_name"]}
        return result
