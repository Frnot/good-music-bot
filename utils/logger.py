import queue
import logging
from logging.handlers import QueueHandler, QueueListener

# TODO: use MemoryHandler to save RPi SD cards (for debug especially)


def init(debug, quiet):
    # QueueHandler is coupled to QueueListener by the queue object
    log_queue = queue.Queue(-1)

    # Configure root (global) logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)
    queue_handler = QueueHandler(log_queue)
    root_logger.addHandler(queue_handler)

    handlers = []

    # Configure logging handlers
    format = logging.Formatter("%(asctime)s %(process)d %(name)-8s : %(levelname)-7s : %(message)s", "%Y%m%d::%H:%M:%S")
    debugformat = logging.Formatter("%(asctime)s %(process)d %(name)-8s : %(funcName)-10s : %(levelname)-7s : %(message)s", "%Y%m%d::%H:%M:%S")

    std_out = logging.StreamHandler()
    std_out.setLevel(logging.INFO)
    std_out.setFormatter(format)
    handlers.append(std_out)

    if not quiet:
        log_file = logging.FileHandler('logs/bot.log', mode='w', encoding="UTF-8")
        log_file.setLevel(logging.INFO)
        log_file.setFormatter(format)
        handlers.append(log_file)

    if debug and not quiet:
        # rotate old debug log file here
        # mv debug.log debug.old.log
        debug_log = logging.FileHandler('logs/debug.log', mode='w', encoding="UTF-8")
        debug_log.setLevel(logging.DEBUG)
        debug_log.setFormatter(debugformat)
        handlers.append(debug_log)

    # Configure queue listener (add handlers to root logger) : QueueHandler ==log_queue==> QueueListener
    global listener
    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()


def start():
    listener.start()


def stop():
    listener.stop()
