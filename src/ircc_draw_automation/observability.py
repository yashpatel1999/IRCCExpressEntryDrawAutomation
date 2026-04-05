import json
import logging
import sys


def get_logger(name="ircc_draw_automation"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(logger, event_type, **fields):
    payload = {"event": event_type}
    payload.update(fields)
    logger.info(json.dumps(payload, sort_keys=True))
