import json
import logging
import os
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


def _runtime_context():
    payload = {}
    commit_sha = os.environ.get("GITHUB_SHA")
    workflow_run_id = os.environ.get("GITHUB_RUN_ID")
    workflow_run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if commit_sha:
        payload["commit_sha"] = commit_sha
    if workflow_run_id:
        payload["workflow_run_id"] = workflow_run_id
    if workflow_run_attempt:
        payload["workflow_run_attempt"] = workflow_run_attempt
    return payload


def log_event(logger, event_type, **fields):
    payload = {"event": event_type}
    payload.update(fields)
    payload.update(_runtime_context())
    line = json.dumps(payload, sort_keys=True)
    logger.info(line)

    log_file = os.environ.get("IRCC_LOG_FILE")
    if log_file:
        directory = os.path.dirname(log_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
