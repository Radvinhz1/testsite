from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import RateLimitBucket


class Command(BaseCommand):
    help = 'Delete expired rate-limit counters (run daily).'

    def handle(self, *args, **options):
        count, _ = RateLimitBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'Deleted {count} expired counters.')
