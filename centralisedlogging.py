import logging
import os

class Logger:
    _logger = None

    @classmethod
    def get_logger(cls, name="AppLogger", log_file="app.log"):
        if cls._logger is None:
            os.makedirs("logs", exist_ok=True)
            full_path = os.path.join("logs", log_file)

            cls._logger = logging.getLogger(name)
            cls._logger.setLevel(logging.DEBUG)

            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

            # File handler
            file_handler = logging.FileHandler(full_path)
            file_handler.setFormatter(formatter)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            cls._logger.addHandler(file_handler)
            cls._logger.addHandler(console_handler)

            cls._logger.debug("Logger initialized.")

        return cls._logger

log = Logger.get_logger()