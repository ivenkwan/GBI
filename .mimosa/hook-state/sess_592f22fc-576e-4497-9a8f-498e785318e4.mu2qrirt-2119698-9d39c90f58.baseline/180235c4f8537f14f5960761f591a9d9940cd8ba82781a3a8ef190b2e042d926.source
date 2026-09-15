"""Logging setup using loguru."""

import sys

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """Configure loguru for structured logging."""
    logger.remove()  # Remove default handler

    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # In production, add JSON log file output
    if settings.APP_ENV == "production":
        logger.add(
            "logs/genbi_{time:YYYY-MM-DD}.json",
            level="INFO",
            serialize=True,
            rotation="1 day",
            retention="30 days",
        )


__all__ = ["logger", "setup_logging"]
