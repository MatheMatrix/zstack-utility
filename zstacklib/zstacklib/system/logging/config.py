from __future__ import annotations

import logging
import os
import gzip
import shutil
import sys
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from typing import TextIO


LOG_FOLDER = "/var/log/zstack"
LOG_FORMAT = "%(asctime)s %(thread)d %(levelname)s [%(name)s] %(message)s"
DEFAULT_MAX_BYTES = 30 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 30


class ZstackRotatingFileHandler(RotatingFileHandler):

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}.gz"
                dfn = f"{self.baseFilename}.{i + 1}.gz"
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)

            dfn = f"{self.baseFilename}.1"
            if os.path.exists(self.baseFilename):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(self.baseFilename, dfn)
                self._compress_log(dfn)

        if not self.delay:
            self.stream = self._open()

    def _compress_log(self, log_path: str) -> None:
        try:
            with open(log_path, "rb") as f_in:
                with gzip.open(f"{log_path}.gz", "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(log_path)
        except Exception:
            pass


@dataclass
class LogConfig:
    log_path: str = os.path.join(LOG_FOLDER, "zstack.log")
    log_level: int = logging.DEBUG
    log_to_console: bool = True
    log_format: str = LOG_FORMAT
    max_bytes: int = DEFAULT_MAX_BYTES
    backup_count: int = DEFAULT_BACKUP_COUNT


_config: LogConfig | None = None
_loggers: dict[str, logging.Logger] = {}


def get_config() -> LogConfig:
    global _config
    if _config is None:
        _config = LogConfig()
    return _config


def configure_log(
    log_path: str,
    level: int = logging.DEBUG,
    log_to_console: bool = False,
) -> None:
    global _config
    log_dir = os.path.dirname(log_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, 0o755)

    _config = LogConfig(
        log_path=log_path,
        log_level=level,
        log_to_console=log_to_console,
    )


def get_logger(name: str, logfd: TextIO | None = None) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    config = get_config()
    logger = logging.getLogger(name)

    if logger.handlers:
        _loggers[name] = logger
        return logger

    logger.setLevel(logging.DEBUG)

    log_dir = os.path.dirname(config.log_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, 0o755)

    file_handler = ZstackRotatingFileHandler(
        config.log_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
    )
    formatter = logging.Formatter(config.log_format)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(config.log_level)
    logger.addHandler(file_handler)

    if config.log_to_console:
        console_handler = logging.StreamHandler(logfd or sys.stdout)
        console_handler.setLevel(config.log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _loggers[name] = logger
    return logger


def get_logfile_path() -> str:
    return get_config().log_path


def set_logfile_path(path: str) -> None:
    get_config().log_path = path
