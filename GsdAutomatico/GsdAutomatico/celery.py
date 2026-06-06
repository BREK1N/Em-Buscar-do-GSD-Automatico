import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GsdAutomatico.settings')

app = Celery('GsdAutomatico')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
