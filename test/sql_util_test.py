import django
import os
import sys
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.sql_util import get_sqlalchemy_engine, execute_sql, query_all_dict, execute_sql_file
from common.logger import Logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'c2matica_py_server.settings')
django.setup()


def test_query_all_dict():
    """测试query_all_dict函数"""
    try:
        assert query_all_dict("SELECT 1;")[0]["1"] == 1, "数据库无法连接"
        assert query_all_dict("SELECT DATABASE();")[
                   0]["DATABASE()"] == 'zhihuishoshudanao', "连接了非目标数据库"
        charset_result = query_all_dict(
            "SHOW VARIABLES LIKE 'character_set_database'")
        assert charset_result[0][
                   "Value"] == 'utf8mb4', f"数据库字符集不是utf8mb4，当前字符集: {charset_result[0]['Value']}"
    except Exception as e:
        raise e


def test_execute_sql():
    """测试execute_sql函数"""
    try:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(50),
            value INT
        )"""
        execute_sql(create_table_sql)
        assert len(query_all_dict(
            "SHOW TABLES LIKE 'test_table'")) > 0, "测试表创建失败"

        params = [("测试1", 100), ("测试2", 200), ("测试2", 300)]
        for param in params:
            assert execute_sql(
                f"INSERT INTO test_table (name, value) VALUES ('{param[0]}', {param[1]})") == 1
        assert len(query_all_dict("SELECT * FROM test_table")) == len(params)

    except Exception as e:
        raise e
    finally:
        execute_sql("DROP TABLE IF EXISTS test_table")


def test_get_sqlalchemy_engine():
    """测试get_sqlalchemy_engine函数"""
    try:
        engine = get_sqlalchemy_engine()
        assert engine is not None, "数据库连接失败"
        df = pd.DataFrame(
            {"name": ["测试1", "测试2", "测试3"], "value": [100, 200, 300]})
        df.to_sql("test_table", engine, if_exists="replace", index=False)
        assert len(query_all_dict("SELECT * FROM test_table")) == 3

    except Exception as e:
        raise e
    finally:
        execute_sql("DROP TABLE IF EXISTS test_table")


def test_execute_sql_from_file():
    """测试execute_sql_from_file函数"""
    try:
        assert execute_sql_file("./sql/fixtures/test_case_0.sql")
    except Exception as e:
        raise e
    finally:
        execute_sql("DROP TABLE IF EXISTS test_table")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
