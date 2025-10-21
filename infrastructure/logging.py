# infrastructure/logging.py
import logging
import sys
from typing import Optional

_FMT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

def configure_logging(level: str = "INFO", propagate: bool = False) -> None:
    """
    Configura logging básico e consistente para todo o projeto.
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_FMT, datefmt=_DATEFMT))
    root.addHandler(handler)

    # Evita logs duplicados ao usar libs que já configuram handlers
    for noisy in ("urllib3", "aiohttp.access"):
        logging.getLogger(noisy).propagate = propagate

def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or __name__)
