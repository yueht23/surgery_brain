# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime
from common.sql_util import query_all_dict, execute_sql, get_sqlalchemy_engine
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
        assert (datetime.strptime(schedule_date, "%Y-%m-%d") >= datetime.
                strptime("2024-09-06", "%Y-%m-%d")), "排程日期必须在2024-09-06之后"
        self.__total_rooms_info = None
        self.__dept_seq_to_room_id = self.__get_dept_seq_to_room_id_df()
        self.sqlalchemy_engine = get_sqlalchemy_engine()
        self.logger.info("ScheduleIO initialized.")

    def import_surgeries(self):
        """
        从surgericalapplicationinfo_port表中导入手术并预处理手术数据到
        surgicalapplicationinfo_python表中，方便后续排程
        :return:
        """
        execute_sql("DROP TABLE IF EXISTS surgicalapplicationinfo_python")

        sql = """
            SELECT DISTINCT-- 去重
            -- --------------------------------
            -- --------------------------------
            --       原手术申请表字段        --
            -- --------------------------------
            -- --------------------------------
            sip.ELECTR_REQUISITION_NO AS 'id',-- 手术申请单号
            sip.SURGERY_DATE AS 'surgery_date',-- 拟手术日期
            sip.SURGERY_OPER_NAME AS 'operation_name',-- 手术名称 NOTE: 排程用不到，但是前端需要
            sip.INHOSP_INDEX_NO AS 'admission_number',-- 住院号 NOTE: 排程用不到，但是前端需要, 其与inpatient_serial相同
            sip.INHOSP_INDEX_NO AS 'inpatient_serial',-- 住院流水号
            sip.PAT_NAME AS 'patient_name',-- 患者姓名
            sip.APPLY_DEPT_NAME AS 'apply_dept',-- 申请科室名称
            sip.SURGERY_DR_NAME AS 'surgeon_name',-- 主刀医生姓名
            sip.SURGERY_DR_CODE AS 'surgeon_code',-- 主刀医生id
            sip.SURGERY_TABLE_NO AS 't_seq',-- 台序
            REPLACE ( sip.SURGERY_DURATION, '-小时', '' ) AS 'duration',-- 预估手术时长
            (
              sip.INFECTIOUS_NONE = '1' 
              OR sip.INFECTIOUS_HIV = '1' 
              OR sip.INFECTIOUS_HBV = '1' 
              OR sip.INFECTIOUS_HCV = '1' 
              OR sip.INFECTIOUS_AIR = '1' 
              OR sip.INFECTIOUS_OTHER = '1' 
            ) AS 'is_infected',-- 是否感染
            ( sip.oper_typename <> '手术' ) AS 'is_operation',-- 操作非手术
            CASE
                
                WHEN sip.is_mininvasive = '0' THEN
                FALSE 
                  WHEN sip.is_mininvasive = '1' THEN
                TRUE ELSE NULL 
              END AS 'is_mini_invasive',-- 是否微创
            CASE
                
                WHEN sip.IN_STATE = '0' THEN
                FALSE 
                  WHEN sip.IN_STATE = '1' THEN
                TRUE ELSE NULL 
              END AS 'is_admitted',-- 是否已入院, 三阶段排程要用
            CASE
                
                WHEN sip.surgery = '是' THEN
                TRUE ELSE FALSE 
              END AS 'is_day_surgery',-- 是否日间手术
              sip.SURGERY_WOUND_CATEG_CODE AS 'incision_type',-- 切口类型
              REPLACE ( sip.SURGERY_LEVEL_NAME, '级手术', '' ) AS 'surgery_level',-- 手术级别
            -- 四类特殊手术
            CASE
                
                WHEN sip.robot = '是' THEN
                TRUE ELSE FALSE 
              END AS 'is_sp_robot',-- 是否为机器人特殊手术
            CASE
                
                WHEN sip.interventional_operation = '是' THEN
                TRUE ELSE FALSE 
              END AS 'is_sp_intervention',-- 是否为介入特殊手术
            CASE
                
                WHEN sip.perspective = '是' THEN
                TRUE ELSE FALSE 
              END AS 'is_sp_perspective',-- 是否为透视特殊手术
            CASE
                
                WHEN sip.holmium_laser = '是' THEN
                TRUE ELSE FALSE 
              END AS 'is_sp_holmium',-- 是否为钬激光特殊手术
            -- --------------------------------
            -- --------------------------------
            --  新加字段(用于排程结果记录)   --
            -- --------------------------------
            -- --------------------------------
              sip.scheduling_state AS 'arranged_status',-- 排程状态0:未排程,1:一阶段被排程,2:二阶段被排程, 3:三阶段被排程
              si.arrange_operating_room_number AS 'arranged_room_id',-- 安排手术间编号
              si.arrange_operating_number AS 'arranged_room_dept',-- 安排手术部
              si.arrange_operating_room AS 'arranged_room_name',-- 安排手术间
              si.operation_start_time AS 'arranged_start_time',-- 安排手术开始时间
              si.operation_end_time AS 'arranged_end_time', -- 安排手术结束时间
              -- TODO: 失败次数这个先不管
              0 AS 'attempt_times' -- 排程尝试次数
              
            FROM
              surgicalapplication_info_port sip
              INNER JOIN doctor_info di ON di.doctor = sip.SURGERY_DR_NAME
              LEFT JOIN surgicalapplicationinfo si ON sip.ELECTR_REQUISITION_NO = si.application_number  -- 已经排好的手术 
            WHERE
              sip.SURGERY_DATE LIKE '{}%' 
              -- AND ( sip.scheduling_state = FALSE OR sip.scheduling_state IS NULL ) 
              AND sip.SURGERY_DEPT_NAME IN ( '第一手术部', '第二手术部', '日间手术室' ) 
              AND sip.APPLY_DEPT_NAME IN (
                '产科',
                '妇科',
                '耳鼻咽喉头颈外科',
                '骨科关节',
                '骨科脊柱',
                '泌尿外科',
                '胆胰外科',
                '普外甲乳外科',
                '胃肠中心109',
                '胃肠中心209',
                '胃肠中心309',
                '胸外科',
                '普外疝儿外科',
                '肾脏内科',
                '口腔科',
                '创伤中心2',
                '骨科创伤',
                '骨科手足',
                '普外血管外科',
                '神经外科504',
                '神经外科505',
                '神经外科506',
                '心脏大血管病中心',
                '心内科206',
                '心内科306',
                '男科',
                '运动医学科',
                '肝脾外科' 
              ) 
            ORDER BY
              sip.ELECTR_REQUISITION_NO;
                    """.format(self.schedule_date)

        self.logger.info("从surgicalapplicationinfo_port表中导入手术数据到surgicalapplicationinfo_python表中...")
        surgery_table = pd.DataFrame(query_all_dict(sql))

        if not surgery_table.empty:
            self.logger.info("手术数据导入中...,共{}条数据".format(surgery_table.shape[0]))
            self.logger.info("已排手术{}条".format(surgery_table.loc[surgery_table["arranged_status"] > 0].shape[0]))
            self.logger.info("未排手术{}条".format(surgery_table.loc[surgery_table["arranged_status"] == 0].shape[0]))
            # 完成数据类型转换
            surgery_table.to_sql('surgicalapplicationinfo_python',
                                 self.sqlalchemy_engine,
                                 if_exists='replace',
                                 index=False)
            self.logger.info("手术数据导入完成")
        else:
            raise ValueError("没有需要导入的手术，无需排程，检查日期是否正确，当日是否有手术申请")

    def get_weekday(self):
        """
        得到当前日期的星期几，如果是工作日，直接返回，如果是周末，则需要查询mapping_date表。
        :return: int, 星期几，其中1-5代表周一到周五，6-7代表周六到周日
        """
        chinese2num = {'星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, '星期五': 5, '星期六': 6, '星期日': 7}
        date = datetime.strptime(self.schedule_date, "%Y-%m-%d")
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

            if mapping_date.empty or mapping_date.shape[0] != 1:
                raise ValueError("数据库中不存在该日期的映射信息，请检查数据库")
            else:
                strWeekday = mapping_date["week"][0]
                self.logger.info(f"当前日期是周末，需要映射后，是星期{chinese2num[strWeekday]}")
                return chinese2num[strWeekday]

    def get_total_room_info(self):
        """
        返回所有的手术室信息
        例如: room_id = 2586 -> ('第一手术部', '01')
        :param room_id: int, 手术室id
        :return: tuple, 手术室信息, (operating_department, real_name)
        """
        if self.__total_rooms_info is None:
            sql = """
                select 
                      id,
                      operating_department,
                      real_name
                from 
                    operating_room_info
            """
            self.__total_rooms_info = {}
            for row in query_all_dict(sql):
                self.__total_rooms_info[row["id"]] = (row["operating_department"], row["real_name"])
        return self.__total_rooms_info

    def get_room_info_from_id(self, room_id):
        """
        查询room_id对应的手术室信息
        例如: room_id = 2586 -> ('第一手术部', '01')
        :param room_id: int, 手术室id
        :return: tuple, 手术室信息, (operating_department, real_name)
        """
        return self.get_total_room_info()[int(room_id)]

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
            self.logger.info(
                f"科室{dept}{seq_alphabet}当日对应的手术室为{self.get_room_info_from_id(room_id)}{room_id}, 权重为{weight}")
            return room_id, weight

    def __get_applications(self, is_arranged):
        """
        依据arranged_status，获取未安排或者已安排的手术申请
        :return: list[dict], 未安排手术的申请列表
        """
        sql = """
            select 
                *
            from 
                surgicalapplicationinfo_python
            where
                surgery_date like '{}%' AND arranged_status {}
                               """.format(self.schedule_date, "> 0" if is_arranged else "= 0")

        applications = query_all_dict(sql)
        for application in applications:
            application['duration'] = max(round(float(application['duration'])), 0.5)
            application['seq_alphabet'] = application['t_seq'][0]
            application['seq_number'] = int(application['t_seq'][1:])

            if application['arranged_status'] != 0:
                application['arranged_start_time'] = datetime.strptime(application['arranged_start_time'],
                                                                       "%Y-%m-%d %H:%M:%S")
                application['arranged_end_time'] = datetime.strptime(application['arranged_end_time'],
                                                                     "%Y-%m-%d %H:%M:%S")

        return applications

    def get_unarranged_applications(self):
        """
        获取未安排手术的申请
        :return: list[dict], 未安排手术的申请列表
        """
        return self.__get_applications(is_arranged=False)

    def get_arranged_applications(self):
        """
        获取已安排手术的申请
        :return: list[dict], 已安排手术的申请列表
        """
        return self.__get_applications(is_arranged=True)

    def get_available_rooms(self, application):
        """
        获取当前科室的所有可用手术室, 读取科室与手术室的约束表
        :param application: dict, 申请
        :return: list, 可用手术室id列表
        """
        assert isinstance(application, dict)
        assert 'apply_dept' in application
        assert 'is_sp_robot' in application
        assert 'is_sp_intervention' in application
        assert 'is_sp_perspective' in application
        assert 'is_sp_holmium' in application

        if (application['is_sp_robot'] + application['is_sp_intervention'] +
                application['is_sp_perspective'] + application['is_sp_holmium'] > 1):
            self.logger.warning(f"手术申请单号{application['id']}同时为两种特殊手术，需要与医院确认是否有这种情况")

        apply_dept = application['apply_dept']
        is_sp_robot = application['is_sp_robot']
        is_sp_intervention = application['is_sp_intervention']
        is_sp_perspective = application['is_sp_perspective']
        is_sp_holmium = application['is_sp_holmium']

        sp_name = None
        if is_sp_robot:
            sp_name = '机器人'
        elif is_sp_intervention:
            sp_name = '介入手术'
        elif is_sp_perspective:
            sp_name = '透视'
        elif is_sp_holmium:
            sp_name = '钬激光'

        # 如果没有特殊手术，sp_name为None
        if sp_name is None:
            sql = """
            SELECT
              ao.family_name AS apply_dept, -- 申请科室名称
              -- ao.family_code AS apply_dept_code, -- 申请科室名称
              ic.operating_room_id AS room_id-- 手术室ID
            FROM
              administrative_office ao
              JOIN interoperative_constraint ic ON ao.family_code = ic.department 
            WHERE
              ic.whether_can_operation = 1 AND ao.family_name = '{}'
            """.format(apply_dept)
            return [row['room_id'] for row in query_all_dict(sql)]
        else:
            sql = """
            SELECT
              ssr.operating_room_id
            FROM
              special_surgical_info ssi
              JOIN special_surgical_restraint ssr ON ssi.id = ssr.special_id 
            WHERE
              ssr.whether_can_operation AND mapping_name = '{}'
            """.format(sp_name)
            return [row['operating_room_id'] for row in query_all_dict(sql)]

    def write_result_to_db(self, applications):
        """
        回写数据库
        :param applications: list[dict], 申请列表
        """
        for application in applications:
            assert isinstance(application, dict)
            assert application.keys() == {'id',
                                          'arranged_status',
                                          'arranged_room_id',
                                          'arranged_start_time',
                                          'arranged_end_time'}
            assert application['arranged_start_time'] < application['arranged_end_time']

        for application in applications:
            room_dept, room_name = self.get_room_info_from_id(application['arranged_room_id'])
            application['arranged_room_dept'] = room_dept  # e.g. 第一手术部
            application['arranged_room_name'] = room_name  # e.g. 01
            sql = """
                update surgicalapplicationinfo_python
                set 
                    arranged_status = {},
                    arranged_room_id = '{}',
                    arranged_room_dept = '{}',
                    arranged_room_name = '{}',
                    arranged_start_time = '{}',
                    arranged_end_time = '{}'
                where
                    id = '{}'
            """.format(application['arranged_status'],
                       application['arranged_room_id'],
                       application['arranged_room_dept'],
                       application['arranged_room_name'],
                       application['arranged_start_time'],
                       application['arranged_end_time'],
                       application['id'])
            execute_sql(sql)

    def sync_info_python_to_info(self, drop_ratio=0):
        """
        将surgicalapplicationinfo_python表中的数据同步到surgicalapplicationinfo中，同时删除一部分
        注意：此方法只在开发阶段使用，不要在生产环境使用
        :param drop_ratio:  float, 删除比例
        :return:
        """
        # read data from surgicalapplicationinfo_python
        sql = """
            select 
                *
            from 
                surgicalapplicationinfo_python
            where
                arranged_status <> 0 AND surgery_date like '{}%'
        """.format(self.schedule_date)

        df_python = pd.DataFrame(query_all_dict(sql))
        # rename columns to match the columns in surgicalapplicationinfo
        rename_dict = {
            'id': 'application_number',
            'arranged_room_id': 'arrange_operating_room_number',
            'arranged_room_dept': 'arrange_operating_number',
            'arranged_room_name': 'arrange_operating_room',
            'arranged_start_time': 'operation_start_time',
            'arranged_end_time': 'operation_end_time'
        }

        df_python.rename(columns=rename_dict, inplace=True)

        # drop some data
        if drop_ratio > 0:
            df_python = df_python.sample(frac=1 - drop_ratio)

        # write to surgicalapplicationinfo
        df_python.to_sql('surgicalapplicationinfo', self.sqlalchemy_engine, if_exists='replace', index=False)

        # update surgicalapplicationinfo_port scheduling_state as df_python arranged_status
        for row in df_python.itertuples():
            sql = """
                update surgicalapplication_info_port
                set 
                    scheduling_state = {}
                where
                    ELECTR_REQUISITION_NO = '{}'
            """.format(row.arranged_status, row.application_number)
            execute_sql(sql)

    def reset_info_port(self):
        """
        重置surgicalapplication_info_port表中的scheduling_state字段，将所有手术的scheduling_state字段置为0
        注意：此方法只在开发阶段使用，不要在生产环境使用
        :return:
        """
        sql = """
            update surgicalapplication_info_port
            set 
                scheduling_state = 0
            where
                SURGERY_DATE like '{}%'
        """.format(self.schedule_date)
        execute_sql(sql)
        self.logger.info("surgicalapplication_info_port表中的scheduling_state字段重置完成")
