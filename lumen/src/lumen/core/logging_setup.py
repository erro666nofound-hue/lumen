from __future__ import annotations

import logging
import logging.handlers
import sys

from . import paths

_setup_done = False


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with file and stderr handlers (idempotent)."""
    global _setup_done

    if _setup_done:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    log_file = paths.log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)

    def exception_hook(exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions, but let Ctrl-C terminate quietly."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger = logging.getLogger("lumen.uncaught")
        logger.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = exception_hook
    _setup_done = True
