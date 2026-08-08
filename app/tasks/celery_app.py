"""پیکربندی Celery — broker و backend هردو همان Redis پروژه (بدون نیاز به سرویس اضافه)."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "lornux",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.pipeline", "app.tasks.digest"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "poll-sources": {
            "task": "app.tasks.pipeline.poll_sources_task",
            "schedule": settings.poll_interval_minutes * 60.0,
        },
        "daily-digest": {
            "task": "app.tasks.digest.daily_digest_task",
            "schedule": crontab(hour=settings.digest_hour_utc, minute=0),
        },
    },
)
