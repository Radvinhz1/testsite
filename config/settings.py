import os
from pathlib import Path
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'development-only-not-for-production-testsite'
    else:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY or enable local DJANGO_DEBUG=true.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [s for s in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if s]
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'accounts', 'learning',
]
MIDDLEWARE = [
    'learning.seo.IndexingMiddleware',
    'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.RateLimitMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'],
              'APP_DIRS': True, 'OPTIONS': {'context_processors': [
                  'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages', 'learning.seo.metadata_defaults']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DB_ENGINE = os.getenv('DB_ENGINE', 'mssql').lower()
if DB_ENGINE == 'sqlite':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
elif DB_ENGINE == 'mssql':
    DATABASES = {'default': {
        'ENGINE': 'mssql', 'NAME': os.getenv('DB_NAME', 'testsite'),
        # Empty USER/PASSWORD selects Windows Integrated Authentication.
        'USER': os.getenv('DB_USER', ''), 'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'), 'PORT': os.getenv('DB_PORT', ''),
        'OPTIONS': {
            'driver': os.getenv('DB_ODBC_DRIVER', 'ODBC Driver 18 for SQL Server'),
            'extra_params': (
                'Encrypt=yes;TrustServerCertificate=' +
                ('yes' if os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'false').lower() == 'true' else 'no')
            ),
            'isolation_level': 'READ COMMITTED',
            'connection_timeout': 15,
            'connection_retries': 1,
        },
    }}
else:
    raise ImproperlyConfigured('DB_ENGINE must be mssql (SQL Server) or sqlite (local preview).')
AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
# No public media route: every uploaded file is served through an authorized view.
MEDIA_ROOT = Path(os.getenv('PRIVATE_MEDIA_ROOT', str(BASE_DIR / 'private_media')))
MEDIA_URL = '/private-files-not-public/'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'}}
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Enable ONLY behind the trusted, header-overwriting reverse proxy documented in docs.
if os.getenv('TRUST_PROXY_HTTPS', 'false').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
RATE_LIMIT_ENABLED = True

# Set the final HTTPS origin before enabling public indexing.
SITE_URL = os.getenv('SITE_URL', '').strip().rstrip('/')
SEO_INDEXING_ENABLED = os.getenv('SEO_INDEXING_ENABLED', 'false').lower() == 'true'
if SITE_URL:
    site_parts = urlsplit(SITE_URL)
    if (site_parts.scheme != 'https' or not site_parts.hostname or site_parts.path
            or site_parts.query or site_parts.fragment or site_parts.username or site_parts.password):
        raise ImproperlyConfigured('SITE_URL must be an HTTPS origin, e.g. https://example.com (no path).')
if SEO_INDEXING_ENABLED and (not SITE_URL or DEBUG):
    raise ImproperlyConfigured('Public indexing requires SITE_URL and DJANGO_DEBUG=false.')
