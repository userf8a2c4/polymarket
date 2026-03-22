"""
utils/logger.py — Professional logging with loguru
Logging profesional con rotación y colores
"""

import sys
from pathlib import Path

from loguru import logger


def setup_logger(level: str = "INFO", log_file: str = "logs/poly-edge-bot.log",
                 rotation: str = "10 MB", retention: str = "7 days") -> None:
    """Configure loguru logger with console + file sinks.
    Configura loguru con salida a consola y archivo."""

    # Remove default handler / Eliminar handler por defecto
    logger.remove()

    # Console sink with color / Consola con color
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File sink with rotation / Archivo con rotación
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )

    logger.info(f"Logger initialized — level={level}, file={log_file}")
