import logging
import os
import sys
import traceback

from loguru import logger

from paths import BASE_PATH

# Message format shared by every sink.
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)


class InterceptHandler(logging.Handler):
    """Route stdlib `logging` records (e.g. uvicorn) into loguru.

    This is the ONLY stdlib hook: loguru stays the single logging system
    and every record naturally reaches its console / file / GUI sinks.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # Format the exception as plain text instead of passing it to loguru:
        # loguru's "better exceptions" re-evaluates locals in each traceback
        # frame, and some lazy modules (torio's lazy FFmpeg loader) run code in
        # their __repr__, which logs again and can recurse forever. Rendering
        # the traceback here sidesteps that entirely.
        message = record.getMessage()
        if record.exc_info and record.exc_info[0] is not None:
            text = "".join(traceback.format_exception(*record.exc_info)).rstrip()
            if text:
                message = f"{message}\n{text}"
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth).log(level, message)


def setup_logging(
    level: str = "INFO",
    rotation: str = "10 MB",
    retention: str = "30 days",
    file_enabled: bool = True,
    gui_sink=None,
) -> None:
    """Configure loguru as the app's single logging system.

    Adds a colored console sink, a rotating file under Data/logs and an
    optional custom sink (e.g. the GUI websocket broadcaster). Also
    redirects uvicorn's stdlib logging into loguru via InterceptHandler.
    """
    try:
        logger.remove()

        if sys.stderr is not None:
            logger.add(
                sys.stderr,
                format=LOG_FORMAT,
                level=level,
                colorize=True,
                enqueue=True,
            )
        else:
            logger.add(lambda message: None, format="{message}", level=level, enqueue=True)

        if gui_sink is not None:
            logger.add(
                gui_sink,
                format=LOG_FORMAT,
                level=level,
                colorize=True,
                enqueue=True,
            )

        if not file_enabled:
            logger.info("File logging disabled (settings: file_logs=false).")
        else:
            log_dir = os.path.join(BASE_PATH, "Data", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "app.log")
            logger.add(
                log_path,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
                level=level,
                rotation=rotation,
                retention=retention,
                compression="zip",
                encoding="utf-8",
                enqueue=True,
            )
            logger.info(f"Logging initialized. Log file: {log_path}")

        _redirect_stdlib_loggers()
    except Exception as e:
        try:
            logger.exception(f"Failed to configure logging: {e}")
        except Exception:
            print(f"FATAL: failed to configure logging: {e}")
        raise


def _redirect_stdlib_loggers() -> None:
    """Point uvicorn's stdlib loggers at loguru (single pipeline)."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "uvicorn.asgi",
        "torio",
        "torio.io",
        "torio._extension",
        "torchaudio",
    ):
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = [InterceptHandler()]
        stdlib_logger.propagate = False
        # Internal libraries (torio/torchaudio FFmpeg probing, etc.) log a lot
        # of DEBUG/INFO noise; leave their WARNING+ errors visible, quietly drop
        # the rest.
        stdlib_logger.setLevel(logging.WARNING)