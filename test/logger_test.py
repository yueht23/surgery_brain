import pytest
import os
import logging
import shutil
import sys
import datetime


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.logger import Logger


@pytest.fixture(autouse=True, scope="session")
def setup_and_teardown(logger):
    """测试前后的设置和清理"""
    # 设置：确保logs目录存在
    if not os.path.exists("./logs"):
        os.makedirs("./logs")
    
    yield  # 运行测试


    # 接触占用
    # 关闭所有处理器
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    # 重置Logger类的类变量
    Logger._file_handler = None
    # 清理：删除测试产生的日志文件
    assert os.path.exists("./logs")
    for file in os.listdir("./logs"):
        file_path = os.path.join("./logs", file)
        if os.path.isfile(file_path):
            os.remove(file_path)


@pytest.fixture(scope="session")
def logger():
    return Logger("test_logger").get_logger()

def test_logger_initialization(logger):
    """测试日志记录器的初始化"""
    assert logger.name == "test_logger"
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 2  # 应该有一个控制台处理器和一个文件处理器

def test_logger_levels(logger):
    """测试不同日志级别的记录"""
    test_message = "Test message"
    
    # 测试各个日志级别
    logger.debug(test_message)
    logger.info(test_message)
    logger.warning(test_message)
    logger.error(test_message)
    logger.critical(test_message)

def test_log_file_creation(logger):
    """测试日志文件的创建"""
    log_file = f"./logs/log"
    assert os.path.exists(log_file)

def test_logger_format(logger):
    """测试日志消息的格式化"""
    test_message = "Test format message"
    logger.info(test_message)
    
    # 读取日志文件验证格式
    log_file = f"./logs/log"
    with open(log_file, 'r', encoding='utf-8') as f:
        log_content = f.read()
        assert test_message in log_content
        assert "test_logger" in log_content
        assert "INFO" in log_content


def test_diff_loggers():
    logger1 = Logger("logger1").get_logger()
    logger2 = Logger("logger2").get_logger()

    assert logger1.name != logger2.name
    assert id(logger1) != id(logger2)

    assert logger1.handlers[0] != logger2.handlers[0]
    assert isinstance(logger1.handlers[0],logging.StreamHandler)
    assert isinstance(logger2.handlers[0],logging.StreamHandler)

    assert logger1.handlers[1] == logger2.handlers[1]
    assert id(logger1.handlers[1]) == id(logger2.handlers[1])
    assert isinstance(logger1.handlers[1], logging.handlers.TimedRotatingFileHandler)
    assert isinstance(logger2.handlers[1], logging.handlers.TimedRotatingFileHandler)



def test_log_rotation(logger):
    """测试日志文件的轮转功能"""
    # 记录一些初始日志
    logger.info("Initial log message")
    
    # 获取当前日志文件路径
    log_file = "./logs/log"
    assert os.path.exists(log_file)
    
    # 模拟时间变化到第二天
    # 注意：这里我们直接修改 TimedRotatingFileHandler 的 doRollover 方法
    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
            # 强制执行日志轮转
            handler.doRollover()
            break
    
    # 记录新的日志消息
    logger.info("New day log message")
    
    # 检查是否创建了新的日志文件
    # 获取所有日志文件
    log_files = [f for f in os.listdir("./logs") if f.startswith("log")]
    assert len(log_files) >= 2, "应该至少有两个日志文件（当前日志和备份日志）"
    
    # 验证备份日志文件存在
    backup_log = f"./logs/log.{datetime.datetime.now().strftime('%Y-%m-%d')}"
    assert os.path.exists(backup_log), "备份日志文件应该存在"
    
    # 验证两个日志文件都包含预期的内容
    with open(log_file, 'r', encoding='utf-8') as f:
        current_content = f.read()
        assert "New day log message" in current_content
    
    with open(backup_log, 'r', encoding='utf-8') as f:
        backup_content = f.read()
        assert "Initial log message" in backup_content


if __name__ == "__main__":
    pytest.main(["-v", __file__])