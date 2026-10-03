# Validation record

Local automated checks for this implementation:

- Django 5.2.17, Python 3.12, SQLite development database.
- `manage.py check`: passed.
- Initial migrations, sample seeding and repeat seeding: passed.
- `manage.py makemigrations --check --dry-run`: no uncommitted model changes.
- `manage.py collectstatic --noinput`: passed.
- Production-mode `manage.py check --deploy`: no issues with the documented security settings and a temporary validation-only key.
- Test suite: 40 tests discovered; 37 passed and 3 MySQL-specific concurrency tests skipped locally.
- Tests include authorization, grading boundaries, revisions, re-locking, private downloads, certificate revocation, upload validation, profile photo normalization, CSRF, password-reset email, rate limiting and student/admin page rendering.

The GitHub Actions configuration includes SQLite and MySQL 8.4 jobs. The MySQL job runs all tests, including concurrent enrollment, submission and grading with real row locks. See the repository Actions tab for the actual remote result; merely including the workflow is not evidence of a passing MySQL run.

No public deployment, real SMTP delivery or real customer data was used in local tests. Browser validation with headless Chromium: desktop 1440 px and mobile 390 px. Signup → course selection → dashboard → assignment submission succeeded. Home, dashboard and profile had no mobile horizontal overflow and there were no browser page errors. Desktop home and mobile dashboard screenshots were visually inspected.
