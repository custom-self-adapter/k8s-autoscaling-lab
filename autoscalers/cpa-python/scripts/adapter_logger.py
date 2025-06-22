import logging

class AdapterLogger:
    def __init__(self, name: str, level: int = logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        fh = logging.FileHandler("/tmp/adapter.log")
        fh.setLevel(level)
        self.logger.addHandler(fh)
