"""Logging configuration with rotation for Bifrost."""

import gzip
import logging
import os
import shutil
import stat
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class SecureRotatingHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler with gzip compression and secure permissions."""

    def __init__(self, filename, **kwargs):
        super().__init__(filename, when="midnight", backupCount=30, **kwargs)
        # Set secure permissions on log file
        self._secure_file(filename)

    def _secure_file(self, filepath):
        if sys.platform != "win32":
            try:
                os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)  # 0600
            except OSError:
                pass

    def rotator(self, source, dest):
        """Compress rotated log files with gzip."""
        gz_dest = dest + ".gz"
        with open(source, "rb") as f_in:
            with gzip.open(gz_dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
        self._secure_file(gz_dest)

    def namer(self, default_name):
        return default_name + ".gz"


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Set up Bifrost logging with rotation."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "bifrost.log"

    logger = logging.getLogger("bifrost")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not logger.handlers:
        handler = SecureRotatingHandler(str(log_file))
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)

    return logger


def cleanup_old_logs(log_dir: Path, max_age_days: int = 30):
    """Delete compressed log files older than max_age_days."""
    if not log_dir.exists():
        return

    cutoff = time.time() - (max_age_days * 86400)
    for f in log_dir.glob("*.gz"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass
