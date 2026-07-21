"""Celery workers package; exposes the shared Celery application."""

from trend_scout_enterprise.workers.celery_app import celery_app

__all__ = ["celery_app"]
