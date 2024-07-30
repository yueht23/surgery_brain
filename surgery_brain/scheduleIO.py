# -*- coding: utf-8 -*-
import pandas as pd
import datetime
from common.sql_util import query_all_dict, execute_sql
from common.logger import Logger
import re


class ScheduleIO():
    """
    ScheduleIO: Schedule类的所有输入输出操作，Schedule类只负责排程逻辑，不能直接读取与回写数据库。
    """

    def __init__(self, schedule_date):
        self.logger = Logger(__name__).get_logger()
        self.logger.info("ScheduleIO initializing...")

        self.schedule_date = schedule_date
        self.__rooms_id_2_info = None
        self.__dept_seq_to_room_id = self.__get_dept_seq_to_room_id_df()

    def get_weekday(self):
        """
        得到当前日期的星期几，如果是工作日，直接返回，如果是周末，则需要查询mapping_date表。
        :return: int, 星期几，其中1-5代表周一到周五，6-7代表周六到周日
        """
        chinese2num = {'星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, '星期五': 5, '星期六': 6, '星期日': 7}
        date = datetime.datetime.strptime(self.schedule_date, "%Y-%m-%d")
        if date.weekday() in [0, 1, 2, 3, 4]:
            self.logger.info(f"当前日期是工作日,是星期{date.weekday() + 1}")
            return date.weekday() + 1
        else:
            sql = """
                        select 
                               *
                        from mapping_date od
                        where od.date = '{}'
                    """.format(self.schedule_date)
            temp_data = query_all_dict(sql)
            mapping_date = pd.DataFrame(temp_data)
            strWeekday = mapping_date["week"][0]
            self.logger.info(f"当前日期是周末，需要映射后，是星期{chinese2num[strWeekday]}")
            return chinese2num[strWeekday]

    def get_room_info_from_id(self, room_id):
        """
        查询room_id对应的手术室信息
        例如: room_id = 2586 -> ('第一手术部', '01')
        :param room_id: int, 手术室id
        :return: tuple, 手术室信息, (operating_department, real_name)
        """
        if self.__rooms_id_2_info is None:
            sql = """
                select 
                      id,
                      operating_department,
                      real_name
                from 
                    operating_room_info
            """
            self.__rooms_id_2_info = {}
            for row in query_all_dict(sql):
                self.__rooms_id_2_info[row["id"]] = (row["operating_department"], row["real_name"])
        return self.__rooms_id_2_info[room_id]

    def __get_dept_seq_to_room_id_df(self):
        """
        基于手术科室与台序字母，在当前星期，得到该科室的台序字母对应的手术室id
        注意: 此方法不对外暴露，只能类内部调用
        :return: DataFrame, 手术室分配信息，包括科室、台序字母、手术室id、权重
        """
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
            """.format(self.get_weekday())

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
        df = df.astype({'dept': str, 'seq_alphabet': str, 'room_id': int, 'weight': int})
        self.logger.info("当前星期{},当前星期的手术室分配为:\n{}".format(self.get_weekday(), df))
        return df

    def get_room_id_and_weight(self, dept, seq_alphabet):
        """
        根据科室与台序字母,以及当前星期，得到对应的手术室id与权重
        :param dept: 科室
        :param seq_alphabet: 台序字母
        :return: room_id, weight
        """

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

    def get_unarranged_applications(self):
        """
        查询未安排手术的申请, 用于排程
        :return: list[dict], 未安排手术的申请列表
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
                pseudo_operation_data like '{}%' AND arranged = '否'
                               """.format(self.schedule_date)

        unarranged_list = []
        for row in query_all_dict(sql):
            application = {'id': row['id'],
                           'doctor': row['doctor'],
                           'dept': row['dept'],
                           'duration': max(round(float(row['duration'])), 0.5),  # 四舍五入取整,但是至少为0.5小时
                           'seq_alphabet': row['seq'][0],
                           'seq_number': int(row['seq'][1:])
                           }
            unarranged_list.append(application)
        return unarranged_list

    def write_result_to_db(self, applications):
        """
        回写数据库
        :param applications: list[dict], 申请列表
        """
        for application in applications:
            assert isinstance(application, dict)
            assert 'id' in application
            assert 'arranged' in application
            assert 'arranged_room_id' in application
            assert 'arranged_room_dept' in application
            assert 'arranged_room_name' in application
            assert 'arranged_start_time' in application
            assert 'arranged_end_time' in application
            assert application['arranged_start_time'] < application['arranged_end_time']
            # TODO: 其余数据合规性检查

        for application in applications:
            sql = """
                update surgicalapplicationinfo_python
                set 
                    arranged = '{}',
                    arranged_room_id = '{}',
                    arranged_room_dept = '{}',
                    arranged_room_name = '{}',
                    arranged_start_time = '{}',
                    arranged_end_time = '{}'
                where
                    application_number = '{}'
            """.format(application['arranged'],
                       application['arranged_room_id'],
                       application['arranged_room_dept'],
                       application['arranged_room_name'],
                       application['arranged_start_time'],
                       application['arranged_end_time'],
                       application['id'])
            execute_sql(sql)
