from backend.app.core.config import get_settings


def create_celery_app():
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError(
            "celery is required for real publish tasks. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc

    settings = get_settings()
    app = Celery(
        "auto_upt",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["backend.app.tasks.publish"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    return app


celery_app = create_celery_app()
