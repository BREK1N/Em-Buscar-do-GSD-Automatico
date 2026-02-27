from django.core.management.base import BaseCommand
from django.utils import timezone
from Ouvidoria.models import PATD
from datetime import timedelta

class Command(BaseCommand):
    help = 'Deletes PATDs that have been in the trash for more than 30 days.'

    def handle(self, *args, **options):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        expired_patds = PATD.all_objects.filter(
            deleted=True,
            deleted_at__lte=thirty_days_ago
        )
        count = expired_patds.count()
        expired_patds.delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} expired PATDs.'))
