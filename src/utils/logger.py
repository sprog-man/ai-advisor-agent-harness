"""日志记录模块"""

import logging
import sys
from typing import Optional

_configured = False


def setup_logger(name: str = "ai_advisor", level: Optional[str] = None) -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)

    if not _configured:
        log_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(log_level)
        _configured = True

    return logger
