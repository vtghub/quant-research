from __future__ import annotations

from celery import Celery

from quant_research_api.settings import settings

celery_app = Celery("quant_research_api", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
celery_app.autodiscover_tasks(["quant_research_api"])
