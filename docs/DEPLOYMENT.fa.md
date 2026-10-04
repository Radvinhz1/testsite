# راه‌اندازی واقعی سایت

این پروژه در این مرحله روی اینترنت مستقر نشده است. برنامه WSGI و تنظیمات لازم آماده‌اند.

## مراحل

۱. مخزن را روی سرور بگیرید؛ محیط مجازی Python 3.13 و وابستگی‌های requirements-sqlserver.txt را نصب کنید.
۲. SQL Server 2022 و ODBC Driver 18 را نصب و دیتابیس را با docs/sqlserver.sql بسازید. در Linux درایور ODBC مایکروسافت و unixODBC لازم است. کاربر عادی برنامه فقط مجوزهای دیتابیس خودش را داشته باشد. برای Migration به مجوز تغییر ساختار هم نیاز است.
۳. فایل `.env` را با تنظیمات واقعی بسازید:

```dotenv
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=یک_مقدار_تصادفی_طولانی_و_خصوصی
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
DB_ENGINE=mssql
DB_NAME=testsite
DB_USER=testsite
DB_PASSWORD=رمز_خصوصی
DB_HOST=127.0.0.1
DB_PORT=1433
DB_ODBC_DRIVER=ODBC Driver 18 for SQL Server
DB_TRUST_SERVER_CERTIFICATE=false
TRUST_PROXY_HTTPS=true
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=نام_کاربری
EMAIL_HOST_PASSWORD=رمز_خصوصی
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=noreply@example.com
```

دامنه‌ها و SMTP مثال‌اند و باید جایگزین شوند. کلید امن را می‌توان با دستور زیر تولید کرد و در .env گذاشت:

```text
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

۴. پیش از ارتقای دیتابیس موجود پشتیبان بگیرید و برنامه را متوقف کنید؛ اصلاح سیاست قبولی در Migration شماره 0002 برگشت خودکار ندارد. `python manage.py migrate`، `python manage.py seed_courses`، `python manage.py createsuperuser` و `python manage.py collectstatic --noinput` را اجرا کنید. seed_courses به دوره‌های موجود دست نمی‌زند.
۵. `python manage.py check --deploy` را اجرا کنید.
۶. برنامه را با یک process manager و دستور زیر اجرا کنید:

```text
waitress-serve --listen=127.0.0.1:8000 --max-request-body-size=12582912 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
```

۷. در Nginx یا reverse proxy مشابه، HTTPS و گواهی TLS معتبر فعال کنید، درخواست‌ها را به 127.0.0.1:8000 بفرستید، `Host` و `X-Forwarded-Proto` را با مقادیر سرور بازنویسی کنید، و حجم body را حداکثر 12m قرار دهید. تنظیم TRUST_PROXY_HTTPS فقط وقتی مجاز است که مسیر دسترسی مستقیم کاربران به backend بسته باشد و proxy این header را بازنویسی کند.
۸. فقط staticfiles عمومی است. **هیچ location یا alias عمومی برای private_media ایجاد نکنید.** فایل‌های خصوصی از viewهای مجوزدار Django عبور می‌کنند.
۹. یک ثبت‌نام، ارسال تکلیف، نمره‌دهی، بازیابی رمز و دانلود گواهی آزمایشی انجام دهید.

## محدودیت درخواست و نگهداری

محدودیت درخواست داخل برنامه از شمارنده مشترک دیتابیس استفاده می‌کند: حداکثر ۲۰ درخواست POST در هر پنجره ۱۵ دقیقه‌ای برای هر مسیر ورود/ثبت‌نام/بازیابی، و ۱۰ درخواست در دقیقه برای ارسال هر مرحله. در پشت proxy، REMOTE_ADDR ممکن است IP پراکسی باشد؛ header ارسالی کاربر را مستقیم مورد اعتماد قرار ندهید. برای ترافیک عمومی، محدودیت نرخ بر اساس IP واقعی را در پراکسی معتبر هم فعال و تست کنید تا کاربران ناشناس پشت یک IP مشترک بی‌جهت محدود نشوند.

روزانه `python manage.py cleanup_rate_limits` را با cron یا Task Scheduler اجرا کنید. به‌روزرسانی امنیتی وابستگی‌ها، پاک‌سازی فایل‌های قدیمی بدون ارجاع و پایش خطاها جزو نگهداری است. فایل جایگزین‌شده خودکار حذف نمی‌شود تا سابقه از دست نرود؛ پس از پشتیبان‌گیری، فایل‌های بدون ارجاع را با رویه کنترل‌شده پاک کنید.

پشتیبان منظم از SQL Server **و** private_media لازم است؛ یک‌بار بازیابی هر دو را امتحان کنید. کد به‌تنهایی شامل اطلاعات دانشجوها نیست. کلیدها، فایل‌های کاربران و dump دیتابیس را در Git نگه ندارید.

حساب ایمیل واقعی در این تحویل تنظیم نشده است. ارسال بازیابی رمز در انتشار واقعی فقط با SMTP یا backend ایمیل معتبر کار می‌کند. SQLite فقط برای پیش‌نمایش محلی است؛ استقرار عمومی و تست هم‌زمانی با SQL Server انجام شود.
