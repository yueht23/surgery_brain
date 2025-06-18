# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime
from common.sql_util import query_all_dict, execute_sql, get_sqlalchemy_engine
from common.logger import Logger
import re
from math import ceil


class ScheduleIO():
    """
    ScheduleIO: Schedule类的所有输入输出操作，Schedule类只负责排程逻辑，不能直接读取与回写数据库。
    """

    def __init__(self, schedule_date):
        self.logger = Logger(__name__).get_logger()
        self.logger.info("ScheduleIO initializing...")

        self.schedule_date = schedule_date
        self.__total_rooms_info = None
        self.__dept_seq_to_room_id = self.__get_dept_seq_to_room_id_df()
        self.sqlalchemy_engine = get_sqlalchemy_engine()
        self.logger.info("ScheduleIO initialized.")


    def __snapshot(self, prefix, sql, max_cnt=5):
        """
        创建一个带时间戳的快照表，并执行SQL查询将数据复制到快照表。
        同时维护最多max_cnt个快照表，删除最旧的。
        
        Args:
            prefix (str): 快照表名前缀
            sql (str): 要执行的SQL查询语句
            max_cnt (int): 最多保留的快照表数量
            
        Returns:
            str: 新创建的快照表名
        """
        try:
            snapshot_name = f'{prefix}_snapshot_' + datetime.now().strftime("%Y%m%d%H%M%S")
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {snapshot_name}
                AS
                {sql}
            """
            execute_sql(create_sql)
            self.logger.info(f"表快照成功，快照表名为: {snapshot_name}")

            # 获取所有快照表
            list_sql = f"""
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME LIKE '{prefix}_snapshot_%'
            """
            tables = query_all_dict(list_sql)
            tables = [table['TABLE_NAME'] for table in tables]
            self.logger.info(f"{prefix}表快照共计{len(tables)}张")
            
            # 按时间戳排序并删除最旧的表
            tables.sort(key=lambda x: datetime.strptime(x.split("_")[-1], "%Y%m%d%H%M%S"))
            while len(tables) > max_cnt:
                drop_sql = f"""
                    DROP TABLE IF EXISTS {tables[0]}
                """
                execute_sql(drop_sql)
                self.logger.info(f"删除最旧的快照表成功，快照表名为: {tables[0]}")
                tables.pop(0)
                
            return snapshot_name

        except Exception as e:
            self.logger.error(f"{prefix}表快照失败: {e}")

    def import_surgeries(self):
        """
        从surgericalapplicationinfo_port表中导入手术并预处理手术数据到
        surgicalapplicationinfo_python表中，方便后续排程
        :return:
        """
        def get_apply_depts_whitelist():
            """
            获取申请科室白名单
            :return:list[str]
            """
            whitelist = []
            sql = """
            SELECT DISTINCT department_name FROM department_whitelist WHERE is_active = 1
            """
            whitelist = query_all_dict(sql)
            whitelist = [item['department_name'] for item in whitelist]
            self.logger.info("所要纳入排程的申请科室白名单为：" + ",".join(whitelist))
            return whitelist

        def get_room_depts_whitelist():
            """
            获取手术部白名单
            :return:list[str]
            """
            whitelist = []
            sql = """
            SELECT DISTINCT operation_room_name FROM operation_room_whitelist WHERE is_active = 1
            """
            whitelist = query_all_dict(sql)
            whitelist = [item['operation_room_name'] for item in whitelist]
            self.logger.info("所要纳入排程的手术部白名单为：" + ",".join(whitelist))
            return whitelist

        execute_sql("DROP TABLE IF EXISTS surgicalapplicationinfo_python")
        
        self.__snapshot('surgicalapplication_info_port', f"""SELECT * FROM surgicalapplication_info_port WHERE SURGERY_DATE LIKE '{self.schedule_date}%'""")
        self.__snapshot('surgicalapplicationinfo', f""" SELECT * FROM surgicalapplicationinfo WHERE pseudo_operation_data LIKE '{self.schedule_date}%'""")



        sql = f"""
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
              -- sip.INFECTIOUS_NONE = '1' 
              sip.INFECTIOUS_HIV = '1' 
              -- OR sip.INFECTIOUS_HBV = '1' 
              -- OR sip.INFECTIOUS_HCV = '1' 
              OR sip.INFECTIOUS_AIR = '1' 
              -- OR sip.INFECTIOUS_OTHER = '1' 
            ) AS 'is_infected',-- 是否感染
            sip.INFECTIOUS_HIV = '1' AS 'is_infected_hiv',
            sip.INFECTIOUS_AIR = '1' AS 'is_infected_air',
            ( sip.oper_typename <> '手术' ) AS 'is_operation',-- 操作非手术
            CASE
                
                WHEN sip.is_mininvasive = '0' THEN
                FALSE 
                  WHEN sip.is_mininvasive = '1' THEN
                TRUE ELSE NULL 
              END AS 'is_mini_invasive',-- 是否微创
            CASE
                
                WHEN sip.CURR_WARD_NAME = '入院服务中心' THEN
                FALSE 
                  ELSE
                TRUE 
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
              0 AS 'attempt_times', -- 排程尝试次数
              '' AS unarranged_reason-- 未排程原因 TODO:需要从info中抓取
              
            FROM
              surgicalapplication_info_port sip
              INNER JOIN doctor_info di ON di.doctor = sip.SURGERY_DR_NAME
              LEFT JOIN surgicalapplicationinfo si ON sip.ELECTR_REQUISITION_NO = si.application_number  -- 已经排好的手术 
            WHERE
              sip.SURGERY_DATE LIKE '{self.schedule_date}%' 
              -- AND ( sip.scheduling_state = FALSE OR sip.scheduling_state IS NULL ) 
              AND sip.SURGERY_DEPT_NAME IN ( {",".join(f"'{item}'" for item in get_room_depts_whitelist())} ) 
              AND sip.APPLY_DEPT_NAME IN ({",".join(f"'{item}'" for item in get_apply_depts_whitelist())}) 
            ORDER BY
              sip.ELECTR_REQUISITION_NO;
                    """
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
            _ = len(query_all_dict("SELECT * FROM surgicalapplicationinfo_python"))
            if _ != len(surgery_table):
                raise ValueError("存在{}条数据导入失败，请检查数据库".format(len(surgery_table) - _))
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
        # 为了更好的日志输出
        df_print = df.copy()
        df_print["operating_department"] = df["room_id"].apply(lambda x: self.get_room_info_from_id(x)[0])
        df_print["real_name"] = df["room_id"].apply(lambda x: self.get_room_info_from_id(x)[1])
        df_print = df_print[["operating_department", "real_name", "dept", "seq_alphabet", "room_id", "weight"]]
        df_print = df_print.sort_values(by=["operating_department", "real_name"])
        self.logger.info("当前星期{},当前星期的手术室分配为:\n".format(self.get_weekday()))
        for row in str(df_print).split("\n"):
            self.logger.info(row)
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

            modified_duration = max(ceil(float(application['duration']) * 2) / 2, 0.5)
            if abs(float(application['duration']) - modified_duration) > 0.1:
                self.logger.warning("手术{}的时长{}被修改为{}".format(application['id'],
                                                                      application['duration'],
                                                                      modified_duration))

            application['duration'] = modified_duration
            application['seq_alphabet'] = application['t_seq'][0]
            application['seq_number'] = int(application['t_seq'][1:])

            if application['arranged_status'] != 0:
                try:
                    application['arranged_start_time'] = datetime.strptime(application['arranged_start_time'],"%Y-%m-%d %H:%M:%S")
                    application['arranged_end_time'] = datetime.strptime(application['arranged_end_time'],"%Y-%m-%d %H:%M:%S")
                except ValueError as e:
                    raise ValueError("手术申请{}的arranged_status!=0,但是其arranged_start_time，arranged_end_time格式错误，错误为：{}".format(application,e))
            else:
                if application['arranged_start_time'] != "" or application['arranged_start_time'] != None:
                    application['arranged_start_time'] = None
                    self.logger.warning("手术申请{}的arranged_status=0,但是其arranged_start_time不为空，请检查".format(application))    
                if application['arranged_end_time'] != "" or application['arranged_end_time'] != None:
                    application['arranged_end_time'] = None
                    self.logger.warning("手术申请{}的arranged_status=0,但是其arranged_end_time不为空，请检查".format(application))


        return applications

    def get_unarranged_applications(self):
        """
        获取未安排手术的申请
        :return: list[dict], 未安排手术的申请列表
        """
        unarranged_applications = self.__get_applications(is_arranged=False)
        for app in unarranged_applications:
            try:
                assert app["arranged_status"] == 0
                assert app["arranged_room_id"] is None
                assert app["arranged_room_dept"] is None
                assert app["arranged_room_name"] is None
                assert app["arranged_start_time"] is None
                assert app["arranged_end_time"] is None
            except Exception as e:
                self.logger.error(f"未排程手术{app['id']}的信息有误，错误为：{e}")
                raise ValueError(f"未排程手术{app['id']}的信息有误，错误为：{e}")
        return unarranged_applications

    def get_arranged_applications(self):
        """
        获取已安排手术的申请
        :return: list[dict], 已安排手术的申请列表
        """
        arranged_applications = self.__get_applications(is_arranged=True)
        for app in arranged_applications:
            try:
                assert app["arranged_status"] > 0
                assert app["arranged_room_id"] is not None and app["arranged_room_id"] != ""
                assert app["arranged_room_dept"] is not None and app["arranged_room_dept"] != ""
                assert app["arranged_room_name"] is not None and app["arranged_room_name"] != ""
                assert app["arranged_start_time"] is not None and isinstance(app["arranged_start_time"],datetime)
                assert app["arranged_end_time"] is not None and isinstance(app["arranged_end_time"],datetime)
                assert app["arranged_start_time"] < app["arranged_end_time"]
            except Exception as e:
                self.logger.error(f"已排程手术{app['id']}的信息有误，错误为：{e}")
                raise ValueError(f"已排程手术{app['id']}的信息有误，错误为：{e}")
        return arranged_applications

    def get_available_rooms(self, application):
        """
        获取当前申请的所有可用手术室，将可用手术间id以列表返回
        其主要逻辑如下：
        1. 该手术是不是空气感染，如果是，则直接放在一部23号
        2. 该手术是不是四类特殊手术，如果是，则采用特殊手术的约束表
        3. 该手术不属于以上两者，则直接用科室的约束表
        :param application: dict, 申请
        :return: List[str], 可用手术间id列表
        """
        assert isinstance(application, dict)
        assert 'apply_dept' in application
        assert 'is_sp_robot' in application
        assert 'is_sp_intervention' in application
        assert 'is_sp_perspective' in application
        assert 'is_sp_holmium' in application
        assert 'is_infected_air' in application

        if application["is_infected_air"]:
            # TODO: 一部23号
            # 当前逻辑是写死的，需要前端可改
            return ["2619"]



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
            self.logger.info("当前手术不是特殊手术，采用科室的约束表")
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
            available_rooms = [row['room_id'] for row in query_all_dict(sql)]
        else:
            self.logger.info(f"当前手术是特殊手术{sp_name}，采用特殊手术的约束表")
            sql = """
            SELECT
              ssr.operating_room_id
            FROM
              special_surgical_info ssi
              JOIN special_surgical_restraint ssr ON ssi.id = ssr.special_id 
            WHERE
              ssr.whether_can_operation AND mapping_name = '{}'
            """.format(sp_name)
            available_rooms = [row['operating_room_id'] for row in query_all_dict(sql)]

        return available_rooms

    def write_result_to_db(self, applications):
        """
        回写数据库
        :param applications: list[dict], 申请列表
        """
        self.logger.info("回写数据库")
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
            
        self.__snapshot('surgicalapplicationinfo_python', f""" SELECT * FROM surgicalapplicationinfo_python""",max_cnt=10)
        self.logger.info("回写数据库完成")

    def update_unscheduled_reason(self, id, reason, append=False):
        """
        更新未排程手术的原因
        :param id: 手术申请单号
        :param reason: 未排程原因
        :param append: 是否追加原因
        :return: None
        """
        try:
            if append:
                sql = f"""
                    update surgicalapplicationinfo_python
                    set
                        unarranged_reason = concat(unarranged_reason, ';{reason}')
                    where
                        id = '{id}'
                """
            else:
                sql = f"""
                    update surgicalapplicationinfo_python
                    set 
                        unarranged_reason = '{reason}'
                    where
                        id = '{id}'
                """
            execute_sql(sql)
            _ = "追加" if append else "更新"
            self.logger.info(f"{_} 手术 {id} 的未排程原因为: {reason}")


        except Exception as e:
            self.logger.error(f"更新手术 {id} 的未排程原因失败: {e}")

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
            'surgery_date':'pseudo_operation_data',
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

    def validation_check(self):
        """
        用于检测手术排程的合法性
        :return:
        """
        try:
            self.logger.info("开始进行排程结果的合法性检查")
            sql = "select * from surgicalapplicationinfo_python"
            applications = query_all_dict(sql)
            df_applications = pd.DataFrame(applications)

            df_applications["arranged_start_time"] = pd.to_datetime(df_applications["arranged_start_time"])
            df_applications["arranged_end_time"] = pd.to_datetime(df_applications["arranged_end_time"])

            df_arranged = df_applications.loc[df_applications["arranged_status"] > 0]

            if not (df_arranged["arranged_end_time"].dt.hour <= 20).all():
                invalid_id_set = df_arranged.loc[df_arranged["arranged_end_time"].dt.hour > 20]["id"].tolist()
                self.logger.error("排程结果有误，最晚结束时间晚于20:00, id:{}".format(invalid_id_set))
            if not (df_arranged["arranged_start_time"].dt.hour >= 8).all():
                invalid_id_set = df_arranged.loc[df_arranged["arranged_start_time"].dt.hour < 8]["id"].tolist()
                self.logger.error("排程结果有误，最早开始时间早于8:00, id:{}".format(invalid_id_set))
            if not (df_arranged["arranged_start_time"] < df_arranged["arranged_end_time"]).all():
                invalid_id_set = \
                    df_arranged.loc[df_arranged["arranged_start_time"] >= df_arranged["arranged_end_time"]][
                        "id"].tolist()
                self.logger.error("排程结果有误，开始时间大于结束时间, id:{}".format(invalid_id_set))

            # 每个手术室（arranged_room_id） 的手术不重叠
            for room_id in df_arranged["arranged_room_id"].unique():
                df_room = df_arranged.loc[df_arranged["arranged_room_id"] == room_id]
                df_room = df_room.sort_values(by="arranged_start_time")
                if not (df_room["arranged_start_time"].shift(-1) >= df_room["arranged_end_time"])[:-1].all():
                    self.logger.error(f"手术室 {self.get_room_info_from_id(room_id)} 的手术时间存在重叠")

            # 每个医生（surgeon_code） 的手术不重叠
            for surgeon_code in df_arranged["surgeon_code"].unique():
                df_surgeon = df_arranged.loc[df_arranged["surgeon_code"] == surgeon_code]
                df_surgeon = df_surgeon.sort_values(by="arranged_start_time")
                if not (df_surgeon["arranged_start_time"].shift(-1) >= df_surgeon["arranged_end_time"])[:-1].all():
                    self.logger.error(f"医生 {surgeon_code} 的手术时间存在重叠")

            self.logger.info("排程结果的合法性检查完成")

        except Exception as e:
            self.logger.error("排程结果的合法性检查出错，请检查排程结果")
