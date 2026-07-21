"""Shared Celery application instance for all Trend Scout Enterprise workers."""

import os

from celery import Celery

from trend_scout_enterprise.core.config import settings

celery_app = Celery(
    "trend_scout_enterprise",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Task modules are imported lazily via `include` to avoid circular imports:
    # the worker modules import this module to register their tasks on it.
    include=[
        "trend_scout_enterprise.workers.scan_worker",
        "trend_scout_enterprise.workers.report_worker",
        "trend_scout_enterprise.workers.beat_scheduler",
    ],
)

celery_app.conf.update(
    task_soft_time_limit=300,
    task_time_limit=600,
    worker_max_tasks_per_child=100,
)

# Run tasks in-process only under tests or when explicitly requested.
celery_app.conf.task_always_eager = settings.testing or os.environ.get("CELERY_EAGER") == "1"

# Eagerly import the modules listed in `include` so tasks are registered as soon as
# this module is imported (safe: the `celery_app` name is already bound above, so the
# worker modules' `from ...celery_app import celery_app` does not cause a cycle).
celery_app.loader.import_default_modules()
