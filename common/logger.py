import logging
from logging.handlers import TimedRotatingFileHandler
import os


class Logger:
    # 类级别的共享 file_handler
    _file_handler = None
    
    def __init__(self, name, level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        log_file = "./logs/log"
        if not os.path.exists(os.path.dirname(log_file)):
            os.makedirs(os.path.dirname(log_file))

        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - (%(filename)s:%(lineno)d) - %(levelname)s - %(message)s')

            # 如果还没有创建 file_handler，则创建一个新的
            if not Logger._file_handler:
                Logger._file_handler = TimedRotatingFileHandler(
                    log_file, 
                    when='midnight', 
                    interval=1, 
                    backupCount=30, 
                    encoding='utf-8')
                Logger._file_handler.setLevel(level)
                Logger._file_handler.setFormatter(formatter)

            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self.logger.addHandler(Logger._file_handler)

    def get_logger(self):
        return self.logger
