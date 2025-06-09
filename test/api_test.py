import os
import sys
import threading
import time
import pytest
import pymysql
import requests
import pandas as pd
from waitress import serve
from sqlalchemy import text
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from c2matica_py_server.wsgi import application
from common.logger import Logger
from common.sql_util import get_sqlalchemy_engine, execute_sql, query_all_dict


# 测试服务器的配置
TEST_HOST = "localhost"
TEST_PORT = 8002
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}/surgery_brain"



@pytest.fixture(scope="module", autouse=True)
def server():
    # 在测试模块开始时启动服务器
    logger = Logger(__name__).get_logger()
    logger.info("Starting c2matica_py_server")
    
    thread = threading.Thread(
        target=lambda: serve(application, host=TEST_HOST, port=TEST_PORT),
        daemon=True
    )
    thread.start()
    
    # 等待服务器启动（防止立即请求时服务器未就绪）
    time.sleep(1)
    print("服务器启动成功")
    yield
    # 测试结束后，Waitress 会随进程结束（daemon=True）



def test_hello_world_endpoint():
    """测试hello_world接口的GET和POST请求"""
    # 测试GET请求
    get_response = requests.get(f"{BASE_URL}/hello_world")
    assert get_response.status_code == 200
    assert get_response.text == "GET:hello world"

    # 测试POST请求
    test_data = {"message": "test"}
    post_response = requests.post(f"{BASE_URL}/hello_world", json=test_data)
    assert post_response.status_code == 200
    assert post_response.text == f"POST: hello world,{test_data}"


if __name__ == "__main__":
    pytest.main(["-v", __file__])