"""
پیکربندی لاگ مرکزی. از loguru استفاده می‌کنیم چون setup آن ساده‌تر از logging استاندارد
و برای پروژه‌ای با چند process (celery worker, beat, bot) کافی است.
"""
import sys

from loguru import logger

logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)
logger.add(
    "logs/lornux_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="00:00",
    retention="14 days",
    encoding="utf-8",
)

__all__ = ["logger"]
