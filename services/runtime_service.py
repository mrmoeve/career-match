import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = "career_match"


def configure_logging(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(os.getenv("APP_LOG_LEVEL", "INFO").upper())
    logger.propagate = False

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def init_monitoring() -> None:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("APP_ENV", "production")),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        )
    except Exception:
        logging.getLogger(LOGGER_NAME).exception("Unable to initialize Sentry monitoring.")


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
