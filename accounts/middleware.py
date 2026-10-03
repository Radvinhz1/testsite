import hashlib
import time
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from .models import RateLimitBucket


class RateLimitMiddleware:
    """Shared database counters; never trust a client-supplied X-Forwarded-For."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and settings.RATE_LIMIT_ENABLED:
            auth_paths = {'/accounts/login/', '/accounts/signup/', '/accounts/password-reset/', '/admin/login/'}
            if request.path in auth_paths or request.path.startswith('/stages/'):
                interval = 900 if request.path in auth_paths else 60
                limit = 20 if interval == 900 else 10
                identity = str(request.user.pk) if request.user.is_authenticated else request.META.get('REMOTE_ADDR', '')
                key = hashlib.sha256(f'{identity}:{request.path}:{int(time.time()) // interval}'.encode()).hexdigest()
                with transaction.atomic():
                    RateLimitBucket.objects.get_or_create(key=key, defaults={'expires_at': timezone.now() + timedelta(seconds=interval)})
                    bucket = RateLimitBucket.objects.select_for_update().get(pk=key)
                    bucket.count += 1
                    bucket.save(update_fields=['count'])
                if bucket.count > limit:
                    response = HttpResponse('تعداد درخواست‌ها زیاد است؛ چند دقیقه بعد دوباره تلاش کنید.', status=429)
                    response['Retry-After'] = str(interval)
                    return response
        response = self.get_response(request)
        if request.user.is_authenticated:
            response['Cache-Control'] = 'private, no-store'
        return response
