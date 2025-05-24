import os
import sys
import pytest
import django
import traceback
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import Logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'c2matica_py_server.settings')
django.setup()
from common.sql_util import query_all_dict,execute_sql_file,execute_sql
from surgery_brain.schedule2 import Schedule


def validate_schedule_result():
    df = pd.DataFrame(query_all_dict("select * from surgicalapplicationinfo_python"))

    df["arranged_start_time"] = pd.to_datetime(df["arranged_start_time"])
    df["arranged_end_time"] = pd.to_datetime(df["arranged_end_time"])
    df_arranged = df.loc[df["arranged_status"] > 0]
    df_unarranged = df.loc[df["arranged_status"] == 0]

    errors = []
    if not (df_arranged["arranged_start_time"].dt.hour >= 8).all():
        invalid_id_set = df_arranged.loc[df_arranged["arranged_start_time"].dt.hour < 8]["id"].tolist()
        errors.append(f"排程结果有误，最早开始时间早于8:00, id:{invalid_id_set}")

    if not (df_arranged["arranged_start_time"].dt.hour <= 20).all():
        invalid_id_set = df_arranged.loc[df_arranged["arranged_start_time"].dt.hour > 20]["id"].tolist()
        errors.append(f"排程结果有误，尾台手术开始时间晚于20:00, id:{invalid_id_set}")

    if not (df_arranged["arranged_start_time"] < df_arranged["arranged_end_time"]).all():
        invalid_id_set = df_arranged.loc[df_arranged["arranged_start_time"] >= df_arranged["arranged_end_time"]]["id"].tolist()
        errors.append(f"排程结果有误，开始时间大于结束时间, id:{invalid_id_set}")

    for room_id in df_arranged["arranged_room_id"].unique():
        df_room = df_arranged.loc[df_arranged["arranged_room_id"] == room_id]
        df_room = df_room.sort_values(by="arranged_start_time")
        if not (df_room["arranged_start_time"].shift(-1) >= df_room["arranged_end_time"])[:-1].all():
            errors.append(f"手术室 {room_id} 的手术时间存在重叠")
    
    if len(df_unarranged.loc[df_unarranged["unarranged_reason"].isna()]) > 0:
        invalid_id_set = df_unarranged.loc[df_unarranged["unarranged_reason"].isna()]["id"].tolist()
        errors.append(f"未排程手术不存在未排程原因, id:{invalid_id_set}")

    CLEAN_ROOM_ID = "2619" # 洁净手术间，一部23号，ID：2619
    if len(df_arranged.loc[(df_arranged["is_infected_air"]== 1) & (df_arranged["arranged_room_id"] != CLEAN_ROOM_ID)]) > 0:
        invalid_id_set = df_arranged.loc[(df_arranged["is_infected_air"]== 1) & (df_arranged["arranged_room_id"] != CLEAN_ROOM_ID)]["id"].tolist()
        errors.append(f"空气感染手术排程在洁净手术间，id:{invalid_id_set}")
    
    # 检查HIV感染手术是不是该医生在该术间的最后的手术
    # 换言之，该手术后面是不应该有该医生的非HIV感染手术
    for _, row in df_arranged.loc[(df_arranged["is_infected_hiv"]==1)].iterrows():
        mask = df_arranged["arranged_room_id"] == row["arranged_room_id"]
        mask &= df_arranged["surgeon_code"] == row["surgeon_code"]
        mask &= df_arranged["is_infected_hiv"] == 0
        mask &= df_arranged["arranged_end_time"] > row["arranged_end_time"]
        if len(df_arranged.loc[mask]) > 0:
            errors.append(f"HIV感染手术不是该医生在该术间的最后一台手术, id:{row['id']}")
  
    return errors


@pytest.mark.order(1)
@pytest.mark.parametrize("schedule_date", ["2025-04-15", "2025-04-16", "2025-04-17"])
def test_schedule_first_basic(schedule_date):
    """测试一期确定性排程"""
    logger = Logger(__name__).get_logger()
    logger.info(f"开始测试一期排程,排程日期:{schedule_date}")

    try:
        # 准备测试数据
        assert execute_sql_file("./sql/setup/init.sql")
        assert execute_sql_file("./sql/fixtures/test_case_1.sql")

        schedule = Schedule(schedule_date)
        schedule.schedule_first()
        schedule.gantt_chart()

        # 验证排程结果
        errors = validate_schedule_result()
        assert len(errors) == 0, f"排程结果验证失败: {errors}"
        
    except Exception as e:
        logger.error("一期排程测试失败,错误详情如下:")
        logger.error(traceback.format_exc())
        raise e
    finally:
        execute_sql_file("./sql/teardown/cleanup.sql")


@pytest.mark.order(2)
@pytest.mark.parametrize("schedule_date", ["2025-04-15", "2025-04-16", "2025-04-17"])
def test_schedule_second_basic(schedule_date):
    """测试二期抢单排程"""
    logger = Logger(__name__).get_logger()
    logger.info(f"开始测试二期排程,排程日期:{schedule_date}")

    try:
        # 准备测试数据
        assert execute_sql_file("./sql/setup/init.sql")
        assert execute_sql_file("./sql/fixtures/test_case_1.sql")

        # 执行一期排程
        schedule = Schedule(schedule_date)
        schedule.schedule_first()

        # 模拟后端行为
        schedule.sio.sync_info_python_to_info(drop_ratio=0) 
        

        # 执行二期排程
        schedule. schedule_sec()
        schedule.gantt_chart()

        # 验证排程结果
        errors = validate_schedule_result()
        assert len(errors) == 0, f"排程结果验证失败: {errors}"
        
    except Exception as e:
        logger.error("一期排程测试失败,错误详情如下:")
        logger.error(traceback.format_exc())
        raise e
    finally:
        execute_sql_file("./sql/teardown/cleanup.sql")   



@pytest.mark.order(2)
@pytest.mark.parametrize("schedule_date", ["2025-04-15", "2025-04-16", "2025-04-17"])
def test_schedule_second_infectious(schedule_date):
    """
    测试二期抢单排程,考虑到感染手术
    """
    logger = Logger(__name__).get_logger()
    logger.info(f"开始测试二期排程,排程日期:{schedule_date}")

    try:
        # 准备测试数据
        assert execute_sql_file("./sql/setup/init.sql")
        assert execute_sql_file("./sql/fixtures/test_case_1.sql")
        execute_sql("""UPDATE surgicalapplication_info_port SET INFECTIOUS_AIR = 1 WHERE MOD(ELECTR_REQUISITION_NO, 11) = 0;""")
        execute_sql("""UPDATE surgicalapplication_info_port SET INFECTIOUS_HIV = 1 WHERE MOD(ELECTR_REQUISITION_NO, 10) = 0;""")
        
        # 验证改日有感染手术
        infected_surgeries = query_all_dict(f"""
            SELECT COUNT(*) as count 
            FROM surgicalapplication_info_port 
            WHERE SURGERY_DATE LIKE '{schedule_date}%'
            AND (INFECTIOUS_AIR = 1 OR INFECTIOUS_HIV = 1)
        """)
        assert infected_surgeries[0]['count'] > 0, f"日期 {schedule_date} 没有被构造感染手术"


        # 执行一期排程
        schedule = Schedule(schedule_date)
        schedule.schedule_first()

        # 模拟后端行为
        schedule.sio.sync_info_python_to_info(drop_ratio=0) 
        

        # 执行二期排程
        schedule. schedule_sec()
        schedule.gantt_chart()

        # 验证排程结果
        errors = validate_schedule_result()
        assert len(errors) == 0, f"排程结果验证失败: {errors}"
        
    except Exception as e:
        logger.error("一期排程测试失败,错误详情如下:")
        logger.error(traceback.format_exc())
        raise e
    finally:
        execute_sql_file("./sql/teardown/cleanup.sql")   



if __name__ == "__main__":
    pytest.main(["-v", __file__])
