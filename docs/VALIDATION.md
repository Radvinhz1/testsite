# Validation record — SQL Server edition

Current requirements: Microsoft SQL Server, manual administrator grading, passing score >=70.

Local checks (Python 3.12, Django 5.2.17, SQLite preview):

- 42 tests discovered; 39 passed, 3 SQL Server concurrency tests skipped on SQLite.
- Added exact-70 progression through all four stages and an existing-data policy-upgrade test.
- Existing tests cover private files, authorization, manual grading, revisions, re-locking, certificates, profiles and password reset.

The workflow now uses SQL Server 2022 with ODBC Driver 18 and mssql-django 2.0.0. The SQL Server job installs the driver, creates a database, runs migrations and seeding, then runs all tests including concurrent enrollment/submission/review. A successful run will be recorded below after verification.

The earlier MySQL run (37148168177) validated the previous edition only; it is not evidence of SQL Server compatibility. Public deployment and real SMTP configuration are not part of these tests.
