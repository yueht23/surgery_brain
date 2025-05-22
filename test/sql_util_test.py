import os
import sys
import pytest
import pandas as pd
from waitress import serve
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from c2matica_py_server.wsgi import application
from common.logger import Logger
from common.sql_util import get_sqlalchemy_engine, execute_sql, query_all_dict




def test_sql_util_functions():
    """测试数据库工具函数"""
    logger = Logger(__name__).get_logger()
    logger.info("开始测试数据库工具函数")

    try:
        # 测试execute_sql函数
        # 创建测试表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(50),
            value INT
        )
        """
        execute_sql(create_table_sql)
        logger.info("测试表创建成功")

        # 插入测试数据
        params = [("测试1", 100), ("测试2", 200),("测试2", 300)]
        for param in params:
            execute_sql(f"INSERT INTO test_table (name, value) VALUES ('{param[0]}', {param[1]})")
        logger.info("测试数据插入成功")

        # 测试query_all_dict函数
        results = query_all_dict("SELECT * FROM test_table")
        assert len(results) > 0
        logger.info("查询所有数据测试成功")


        # 测试get_sqlalchemy_engine()
        # 创建测试DataFrame
        test_df = pd.DataFrame({
            'name': ['测试A'] * 10000,
            'value': [1000] * 10000
        })
        
        # 使用to_sql写入数据库
        # 清空测试表
        execute_sql("TRUNCATE TABLE test_table")
        logger.info("测试表清空成功")
        assert test_df.to_sql('test_table', con=get_sqlalchemy_engine(), if_exists='append', index=False) == len(test_df)
        logger.info("DataFrame导入测试成功")
        
        # 验证数据导入
        results = query_all_dict("SELECT * FROM test_table WHERE value >= 1000")
        assert len(results) == len(test_df)



        # 清理测试数据
        drop_table_sql = "DROP TABLE IF EXISTS test_table"
        execute_sql(drop_table_sql)
        logger.info("测试表清理成功")

    except Exception as e:
        logger.error(f"数据库工具函数测试失败: {str(e)}")
        raise e



if __name__ == "__main__":
    pytest.main(["-v", __file__])
