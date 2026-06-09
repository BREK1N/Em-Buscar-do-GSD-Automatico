import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GsdAutomatico.settings')

app = Celery('GsdAutomatico')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.broker_connection_retry_on_startup = True
app.autodiscover_tasks()
