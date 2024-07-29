import pandas as pd
from common.logger import Logger
from common.sql_util import query_all_dict, get_sqlalchemy_engine


def do_import_surgery(date):
    sql = """
            SELECT DISTINCT
              -- -------------------------------- 
              --         原手术申请表字段
              -- -------------------------------- 
              
              sip.SURGERY_DATE AS 'pseudo_operation_data', -- 拟手术日期
              sip.ELECTR_REQUISITION_NO AS 'application_number', -- 申请号
              -- sip.INHOSP_INDEX_NO AS 'admission_number', -- 住院号
              sip.PAT_NAME AS 'patient_name', -- 患者姓名
              sip.APPLY_DEPT_NAME AS 'apply_department', -- 申请科室
              sip.SURGERY_DR_NAME AS 'surgeon', -- 主刀医生
              sip.SURGERY_TABLE_NO AS 'table_sequence', -- 台序
              REPLACE(sip.SURGERY_DURATION, '-小时', '') AS 'estimated_duration_operation', -- 预估手术时长
              -- sip.surgery AS 'surgery', -- 是否日间手术
              -- sip.robot AS 'robot', -- 机器人
              -- sip.interventional_operation AS 'interventional_operation', -- 介入手术
              -- sip.perspective AS 'perspective', -- 透视
              -- sip.holmium_laser AS 'holmium_laser', -- 钬激光 
              
              -- -------------------------------- 
              --             新加字段
              -- -------------------------------- 
              
              '否' AS has_arranged, -- 是否已经被排程
              NULL AS second_round_scheduling_weight, -- 二轮排程权重
              NULL AS arrange_operating_room_number, -- 安排手术间编号
              NULL AS arrange_operating_number, -- 安排手术部
              NULL AS arrange_operating_room -- 安排手术间
              
            FROM
              surgicalapplication_info_port sip
              INNER JOIN doctor_info di ON di.doctor = sip.SURGERY_DR_NAME -- AND di.department = sip.APPLY_DEPT_NAME
            WHERE
              sip.SURGERY_DATE LIKE '{}%' 
              AND ( sip.scheduling_state = FALSE OR sip.scheduling_state IS NULL ) 
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
            """.format(date)

    logger = Logger(__name__).get_logger()
    surgeryTable = pd.DataFrame(query_all_dict(sql), dtype=str)
    logger.info("surgeryTable shape:{}".format(surgeryTable.shape))
    logger.info("申请号集合: {}".format(surgeryTable['application_number'].values.tolist()))

    if not surgeryTable.empty:
        surgeryTable.to_sql('surgicalapplicationinfo_python', get_sqlalchemy_engine(), if_exists='replace', index=False)