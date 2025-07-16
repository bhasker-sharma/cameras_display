# camera_app/utils/logging.py

import logging
import os

class Logger:
    _loggers = {}  # Store loggers by name

    @classmethod
    def get_logger(cls, name="AppLogger", log_file="app.log"):
        if name in cls._loggers:
            return cls._loggers[name]

        os.makedirs("logs", exist_ok=True)
        full_path = os.path.join("logs", log_file)

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File handler
        file_handler = logging.FileHandler(full_path, encoding="utf-8")
        file_handler.setFormatter(formatter)

        # Console handler (optional for development)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        if not logger.hasHandlers():
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        logger.debug(f"{name} logger initialized, writing to {log_file}")
        cls._loggers[name] = logger
        return logger

# Default app logger
log = Logger.get_logger()
