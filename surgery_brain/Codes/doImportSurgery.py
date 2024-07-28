import pandas as pd
import datetime
import numpy as np
import time
from common.logger import Logger
from common.sql_util import query_all_dict, get_sqlalchemy_engine

pd.set_option("display.max_columns", None)

# e.g. 20211203

TABLE_HEADER = [
    '拟手术日期',
    '申请号',
    '住院流水号',
    '住院号',
    '患者姓名',
    '手术类别',
    '主刀医生',
    '医生科室',
    '申请科室',
    '手术名称',
    '手术编码',
    '预估手术时长',
    '台序',
    '麻醉方式',
    '是否有手术日',
    '是否为特殊手术',
    '是否已安排',
    '二轮排程权重',
    '安排手术间编号',
    '安排手术部',
    '安排手术间',
    '是否日间手术',  # surgery
    '机器人',  # robot
    '介入手术',  # interventional_operation
    '透视',  # perspective
    '钬激光'  # holmium_laser
]


def doPreprocessSurgery(df):
    try:
        newdf = pd.DataFrame(columns=TABLE_HEADER)
        newdf[['拟手术日期', '申请号', '住院流水号', '住院号', '患者姓名',
               '手术类别', '主刀医生', '申请科室', '手术名称', '手术编码',
               '预估手术时长', '台序', '麻醉方式']] = \
            df[['拟手术日期', '申请号', '住院流水号', '住院号', '姓名',
                '手术类别', '手术者', '申请科室', '手术名称', '手术编码3.0',
                '预估手术时长', '台序', '麻醉方式']].copy()
    except KeyError:
        print('无患者姓名')
        newdf = pd.DataFrame(columns=TABLE_HEADER)
        newdf[['拟手术日期', '申请号', '住院流水号', '住院号',
               '手术类别', '主刀医生', '申请科室', '手术名称', '手术编码',
               '预估手术时长', '台序', '麻醉方式']] = \
            df[['拟手术日期', '申请号', '住院流水号', '住院号',
                '手术类别', '手术者', '申请科室', '手术名称', '手术编码3.0',
                '预估手术时长', '台序', '麻醉方式']].copy()

    newdf[["是否日间手术", "机器人", "介入手术", "透视", "钬激光"]] = df[
        ["是否日间手术", "机器人", "介入手术", "透视", "钬激光"]].replace(
        {"是": "是", "否": "否"}, inplace=False)
    newdf.fillna('', inplace=True)
    newdf.reset_index(drop=True, inplace=True)
    for row in range(len(newdf)):
        _str = newdf.loc[row, '拟手术日期']
        _str = _str.split(' ')[0]
        _str = datetime.datetime.strptime(_str, '%Y/%m/%d')
        _str = datetime.datetime.strftime(_str, '%Y-%m-%d')
        newdf.loc[row, '拟手术日期'] = _str

        _str = newdf.loc[row, '预估手术时长']
        _str = _str.split('-')[0]
        newdf.loc[row, '预估手术时长'] = _str

    # newdf.drop_duplicates(subset=['申请号'], keep='first', inplace=True, ignore_index=True)
    # # 删除申请号重复的行

    # print('经过预处理的表格：111111111111')
    # print(newdf)
    return newdf


def doCheckSpecialSurgery(df):
    sql = """select ssi.mapping_surgical_coding as '映射手术编码' 
    from special_surgical_restraint ssr
             left join special_surgical_info ssi on ssr.special_id = ssi.id
        """
    temp_data = query_all_dict(sql)
    dfConstr = pd.DataFrame(temp_data)
    listSurgeryCode = dfConstr['映射手术编码'].values.tolist()
    for i in range(len(df)):
        if df.loc[i, '手术编码'] in listSurgeryCode:
            df.loc[i, '是否为特殊手术'] = '是'
    # print('经过预处理的表格：22222222222222')
    # print(df)
    return df


def doGenerateAdditionalData(df):
    # # 添加“抢单失败次数”字段
    # # 分别以0.6,0.2,0.1,0.05,0.05的概率填0,1,2,3,4
    # df['抢单失败次数'] = np.random.choice(a=[0, 1, 2, 3, 4], size=len(df),
    #                                       p=[0.4, 0.2, 0.2, 0.1, 0.1]).astype(str)

    # 添加”提交申请时间字段“
    date = datetime.datetime.strptime(df.loc[0, '拟手术日期'], '%Y-%m-%d')
    startTimeStamp = datetime.datetime(date.year, date.month, date.day, 12, 0, 0).timestamp()
    endTimeStamp = datetime.datetime(date.year, date.month, date.day, 18, 0, 0).timestamp()
    df['提交申请时间'] = [''] * len(df)
    for i in range(len(df)):
        tempTime = np.random.randint(startTimeStamp, endTimeStamp)
        tempTime = time.localtime(tempTime)
        print(tempTime)
        tempTime = time.strftime("%Y-%m-%d %H:%M:%S", tempTime)
        df.loc[i, '提交申请时间'] = tempTime

    # 类似地，添加其余字段
    # 取消相关数据字段的随机生成
    # df['是否日间手术'] = np.random.choice(a=['是', '否'], size=len(df), p=[0.2, 0.8])
    # df['机器人'] = np.random.choice(a=['是', '否'], size=len(df), p=[0.05, 0.95])
    # df['介入手术'] = np.random.choice(a=['是', '否'], size=len(df), p=[0.05, 0.95])
    # df['透视'] = np.random.choice(a=['是', '否'], size=len(df), p=[0.05, 0.95])
    # df['钬激光'] = np.random.choice(a=['是', '否'], size=len(df), p=[0.05, 0.95])
    for i in range(1, 30 + 1):
        tempStr = '选择手术间' + str(i)
        df[tempStr] = np.random.choice(a=['是', '否'], size=len(df), p=[1, 0])

    print('经过预处理的表格：44444444444444444')
    print(df)
    return df


def doImportSurgery(df):
    rename_dict = {'拟手术日期': 'pseudo_operation_data',
                   '申请号': 'application_number',
                   '住院流水号': 'hospital_serial_number',
                   '住院号': 'admission_number',
                   '患者姓名': 'patient_name',
                   '手术类别': 'operation_type',
                   '主刀医生': 'surgeon',
                   '医生科室': 'doctor_department',
                   '申请科室': 'apply_department',
                   '手术名称': 'operation_name',
                   '手术编码': 'surgical_coding',
                   '预估手术时长': 'estimated_duration_operation',
                   '台序': 'table_sequence',
                   '麻醉方式': 'mode_anesthesia',
                   '是否有手术日': 'whether_operating',
                   '是否为特殊手术': 'whether_special_operation',
                   '是否已安排': 'has_arranged',
                   '二轮排程权重': 'second_round_scheduling_weight',
                   '安排手术间编号': 'arrange_operating_room_number',
                   '安排手术部': 'arrange_operating_number',
                   '安排手术间': 'arrange_operating_room',
                   '是否日间手术': 'surgery',
                   '机器人': 'robot',
                   '介入手术': 'interventional_operation',
                   '透视': 'perspective',
                   '钬激光': 'holmium_laser',
                   '提交申请时间': 'submission_time',
                   '选择手术间1': 'select_operating_room1',
                   '选择手术间2': 'select_operating_room2',
                   '选择手术间3': 'select_operating_room3',
                   '选择手术间4': 'select_operating_room4',
                   '选择手术间5': 'select_operating_room5',
                   '选择手术间6': 'select_operating_room6',
                   '选择手术间7': 'select_operating_room7',
                   '选择手术间8': 'select_operating_room8',
                   '选择手术间9': 'select_operating_room9',
                   '选择手术间10': 'select_operating_room10',
                   '选择手术间11': 'select_operating_room11',
                   '选择手术间12': 'select_operating_room12',
                   '选择手术间13': 'select_operating_room13',
                   '选择手术间14': 'select_operating_room14',
                   '选择手术间15': 'select_operating_room15',
                   '选择手术间16': 'select_operating_room16',
                   '选择手术间17': 'select_operating_room17',
                   '选择手术间18': 'select_operating_room18',
                   '选择手术间19': 'select_operating_room19',
                   '选择手术间20': 'select_operating_room20',
                   '选择手术间21': 'select_operating_room21',
                   '选择手术间22': 'select_operating_room22',
                   '选择手术间23': 'select_operating_room23',
                   '选择手术间24': 'select_operating_room24',
                   '选择手术间25': 'select_operating_room25',
                   '选择手术间26': 'select_operating_room26',
                   '选择手术间27': 'select_operating_room27',
                   '选择手术间28': 'select_operating_room28',
                   '选择手术间29': 'select_operating_room29',
                   '选择手术间30': 'select_operating_room30'
                   }

    df.rename(columns=rename_dict, inplace=True)
    logger = Logger(__name__).get_logger()
    logger.info("df shape:{}".format(df.shape))
    if not df.empty:
        df.to_sql('surgicalapplicationinfo_python', get_sqlalchemy_engine(), if_exists='replace', index=False)


def do_import_surgery(date):
    # surgeryTable = pd.read_csv(file_path, dtype=str)
    sql = """
            SELECT DISTINCT
            sip.ELECTR_REQUISITION_NO AS '申请号',
            sip.INHOSP_NO AS '住院流水号',
            sip.INHOSP_INDEX_NO AS '住院号',
            sip.SURGERY_PAT_RESOURCE_NAME AS '类别',
            sip.PAT_NAME AS '姓名',
            sip.PHYSI_SEX_NAME AS '性别',
            sip.CURR_BED_NAME AS '床号',
            sip.APPLY_DEPT_NAME AS '申请科室',
            sip.OPERATION_CATEGORY AS '手术类别',
            sip.POSITION AS '部位',
            sip.POSITION_NAME AS '部位名称',
            sip.PRE_SURGERY_DIAG_NAME AS '诊断',
            sip.OPERATION_PREFIX AS '手术前缀',
            sip.SURGERY_OPER_NAME AS '手术名称',
            sip.PRE_SURGERY_DIAG_CODE AS '手术编码3.0',
            sip.OPERATION_SUFFIX AS '手术后缀',
            sip.SURGERY_DR_NAME AS '手术者',
            sip.ANES_METHOD_NAME AS '麻醉方式',
            sip.SURGERY_TABLE_NO AS '台序',
            REPLACE(REPLACE(sip.SURGERY_DATE, 'T', ' '), '-', '/') AS '拟手术日期',
            sip.SURGERY_DEPT_NAME AS '手术室',
            sip.SURGERY_LEVEL_NAME AS '手术级别',
            sip.SURGERY_WOUND_CATEG_CODE AS '切口类型',
            sip.SURGERY_DURATION AS '预估手术时长',
            sip.surgery AS '是否日间手术',
            sip.robot AS '机器人',
            sip.interventional_operation AS '介入手术',
            sip.perspective AS '透视',
            sip.holmium_laser AS '钬激光' 
            FROM
            surgicalapplication_info_port sip 
            INNER JOIN doctor_info di ON di.doctor = sip.SURGERY_DR_NAME -- AND di.department = sip.APPLY_DEPT_NAME
            WHERE
            sip.SURGERY_DATE LIKE '{}%' 
            AND (sip.scheduling_state = FALSE OR sip.scheduling_state IS NULL)
            AND sip.SURGERY_DEPT_NAME IN ('第一手术部', '第二手术部', '日间手术室')
            AND sip.APPLY_DEPT_NAME IN ('产科', '妇科', '耳鼻咽喉头颈外科', '骨科关节', '骨科脊柱', '泌尿外科', '胆胰外科', '普外甲乳外科',
                                        '胃肠中心109', '胃肠中心209', '胃肠中心309', '胸外科', '普外疝儿外科', '肾脏内科', '口腔科',
                                        '创伤中心2', '骨科创伤', '骨科手足', '普外血管外科', '神经外科504', '神经外科505', '神经外科506',
                                        '心脏大血管病中心', '心内科206', '心内科306', '男科', '运动医学科', '肝脾外科')
            ORDER BY
            sip.ELECTR_REQUISITION_NO;  
            """.format(date)

    logger = Logger(__name__).get_logger()
    temp_data = query_all_dict(sql)

    surgeryTable = pd.DataFrame(temp_data, dtype=str)
    logger.info("surgeryTable shape:{}".format(surgeryTable.shape))
    logger.info("申请号集合: {}".format(surgeryTable['申请号'].values.tolist()))

    surgeryTable = doPreprocessSurgery(surgeryTable)
    logger.info("surgeryTable shape:{}".format(surgeryTable.shape))

    surgeryTable = doCheckSpecialSurgery(surgeryTable)
    logger.info("surgeryTable shape:{}".format(surgeryTable.shape))

    surgeryTable = doGenerateAdditionalData(surgeryTable)
    logger.info("surgeryTable shape:{}".format(surgeryTable.shape))

    doImportSurgery(surgeryTable)
