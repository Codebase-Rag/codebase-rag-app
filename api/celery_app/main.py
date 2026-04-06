from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery = Celery(
    "app",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.CELERY_REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.CELERY_REDIS_DB}",
    include=["celery_app.task"],  # Register task module
)

celery.conf.beat_schedule = {
    "sync-sessions-to-postgres": {
        "task": "celery_app.task.sync_session_to_db",
        "schedule": 300.0,  # every 5 minutes
    },
}