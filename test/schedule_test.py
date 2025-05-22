import os
import sys
import threading
import time
import pytest
import pymysql
import requests
import traceback
import pandas as pd
from waitress import serve
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import Logger
from common.sql_util import get_sqlalchemy_engine, execute_sql, query_all_dict
from surgery_brain.schedule2 import Schedule




@pytest.mark.parametrize("schedule_date", ["2025-04-15", "2025-04-16", "2025-04-17"])
def test_schedule_first(schedule_date):
    """测试一期确定性排程"""
    logger = Logger(__name__).get_logger()
    logger.info(f"开始测试一期排程,排程日期:{schedule_date}")
    
    try:
        # 准备测试数据
        sqls = [
            f"UPDATE surgicalapplication_info_port t SET t.scheduling_state = 0 WHERE t.SURGERY_DATE LIKE '{schedule_date}%'",
            "TRUNCATE TABLE surgicalapplicationinfo_python",
            f"DELETE FROM surgicalapplicationinfo WHERE pseudo_operation_data LIKE '{schedule_date}%'"
        ]
        for sql in sqls:
            execute_sql(sql)
        assert len(query_all_dict(f"SELECT * FROM surgicalapplication_info_port WHERE scheduling_state <> 0 AND SURGERY_DATE LIKE '{schedule_date}%'")) == 0
        assert len(query_all_dict(f"SELECT * FROM surgicalapplication_info_port WHERE scheduling_state = 0 AND SURGERY_DATE LIKE '{schedule_date}%'")) > 0
        assert len(query_all_dict("SELECT * FROM surgicalapplicationinfo_python")) == 0
        assert len(query_all_dict(f"SELECT * FROM surgicalapplicationinfo WHERE pseudo_operation_data LIKE '{schedule_date}%'")) == 0


        # 执行一期排程
        schedule = Schedule(schedule_date)
        schedule.schedule_first()
        schedule.gantt_chart()

        # 验证排程结果
        df = pd.DataFrame(query_all_dict("select * from surgicalapplicationinfo_python"))

        df["arranged_start_time"] = pd.to_datetime(df["arranged_start_time"])
        df["arranged_end_time"] = pd.to_datetime(df["arranged_end_time"])
        df_arranged = df.loc[df["arranged_status"] > 0]


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

        

        if not errors:
            logger.info("一期排程测试成功")
        else:
            logger.error("一期排程测试失败,错误详情如下:")
            for error in errors:
                logger.error(error)
            raise Exception(errors)
        
    except Exception as e:
        logger.error("一期排程测试失败,错误详情如下:")
        logger.error(traceback.format_exc())
        raise e
    finally:
        # 清理测试数据
        pass



@pytest.mark.skip(reason="暂时跳过此测试用例")
def test_schedule_sec():
    """测试二期抢单排程"""
    logger = Logger(__name__).get_logger()
    logger.info("开始测试二期排程")
    
    try:
        # 准备测试数据
        schedule_date = "2024-03-20"
        
        # 准备测试数据
        pass
        
        # 执行二期排程
        schedule = Schedule(schedule_date)
        schedule.schedule_sec()
        
        # 验证排程结果
        arranged_applications = query_all_dict("""
            SELECT * FROM surgery_application 
            WHERE apply_date = :date AND arranged_status = 2
        """, {"date": schedule_date})
        
        assert len(arranged_applications) > 0
        logger.info("二期排程测试成功")
        
    except Exception as e:
        logger.error(f"二期排程测试失败: {str(e)}")
        raise e
    finally:
        # 清理测试数据
        pass


if __name__ == "__main__":
    pytest.main(["-v", __file__])
