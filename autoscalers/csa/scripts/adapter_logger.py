import logging

class AdapterLogger:
    def __init__(self, name: str, level: int = logging.INFO):
        sh = logging.StreamHandler()
        sh.setLevel(level)
        fh = logging.FileHandler("/tmp/adapter.log")
        fh.setLevel(level)
        logging.basicConfig(
            level=level,
            format='%(asctime)s %(name)-12s - %(levelname)6s - %(message)s',
            handlers=[fh, sh])
        self.logger = logging.getLogger(name)
