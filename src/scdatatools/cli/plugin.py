import argparse
import logging
import os
import threading

from rich.console import Console
from rich.logging import RichHandler

from scdatatools import __version__


def _colorize(text, _color):
    """Level-name tint placeholder (termcolor was never a declared
    dependency — it only arrived transitively via nubia). RichHandler
    already colorizes levels on the console; keep the text plain."""
    return text


class ErrorFilter(logging.Filter):
    def filter(self, record):
        if record.levelno == logging.INFO:
            return False

        # colorize the level
        level = record.levelname.lower()  # .rjust(8)
        if record.levelno <= logging.DEBUG:
            level = _colorize(level, "blue")
        elif record.levelno >= logging.ERROR:
            level = _colorize(level, "red")
        elif record.levelno >= logging.WARNING:
            level = _colorize(level, "yellow")
        record.level = level

        # logger name
        if record.name == "__main__":
            logger_name = "scdt"
        else:
            logger_name = record.name.split(".")[-1]
        record.logger_name = logger_name

        # thread name (optional)
        record.thread = ""
        if record.levelno <= logging.DEBUG:
            thread = threading.current_thread().getName()
            if thread != "MainThread":
                record.thread = "thread {}: ".format(thread)
        return True


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO


def get_opts_parser(add_help=True):
    """
    Builds the ArgumentParser holding the global scdt options, present on
    every command. Mirrors the pre-argparse shell's global flags exactly.
    """
    opts_parser = argparse.ArgumentParser(
        description=f"scdt - Star Citizen Data Tools v{__version__}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=add_help,
    )
    opts_parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity, can be specified multiple times",
    )
    opts_parser.add_argument(
        "--cache-dir",
        "-C",
        default=None,
        help="Set a cache directory for scdt to use for faster loading times for some commands. The cache directory"
        " can also be set with the SCDT_CACHE_DIR environment variable.",
    )
    return opts_parser


def resolve_cache_dir(args):
    """Apply the --cache-dir / SCDT_CACHE_DIR precedence from the old shell."""
    cache_dir = args.cache_dir
    if cache_dir is None:
        cache_dir = os.environ.get("SCDT_CACHE_DIR", None)
    return cache_dir


def setup_logging(root_logger, args):
    if args.verbose and args.verbose >= 2:
        logging_level = logging.DEBUG
    elif args.verbose == 1:
        logging_level = logging.INFO
    else:
        logging_level = logging.WARN

    # err_fmt = logging.Formatter(fmt="[%(asctime)-15s] [%(level)s] [%(name)s] %(thread)s%(message)s")
    err_console = Console(stderr=True)
    err_handler = RichHandler(console=err_console, rich_tracebacks=True, tracebacks_show_locals=True)
    err_handler.addFilter(ErrorFilter())
    logging.root.addHandler(err_handler)

    std_handler = RichHandler(show_time=False, show_level=False, show_path=False)
    std_handler.addFilter(InfoFilter())
    logging.root.addHandler(std_handler)

    logging.root.setLevel(logging_level)
    return root_logger
