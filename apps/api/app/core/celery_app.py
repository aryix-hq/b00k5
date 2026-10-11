try:
    from celery import Celery
    HAVE_CELERY = True
except ImportError:
    HAVE_CELERY = False
    class Celery:
        def __init__(self, *args, **kwargs):
            self.conf = {}
        def task(self, *args, **kwargs):
            def decorator(f):
                f.delay = f
                return f
            return decorator

from app.core.config import settings

celery_app = Celery(
    "b00k5",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "workers.ocr_worker",
        "workers.compliance_worker",
        "workers.gdrive_sync_worker",
        "app.workers.db_backup_worker"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_routes={
        "workers.ocr_worker.*": {"queue": "ocr_queue"},
        "app.workers.ocr_worker.*": {"queue": "ocr_queue"},
        "workers.compliance_worker.*": {"queue": "compliance_queue"},
        "app.workers.compliance_worker.*": {"queue": "compliance_queue"},
        "workers.gdrive_sync_worker.*": {"queue": "gdrive_queue"},
        "app.workers.gdrive_sync_worker.*": {"queue": "gdrive_queue"},
        "tasks.backup_database_to_gdrive": {"queue": "gdrive_queue"},
    }
)
