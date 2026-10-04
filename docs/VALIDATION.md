# Validation record — SQL Server edition

Current requirements: Microsoft SQL Server, manual administrator grading, passing score >=70.

Local checks (Python 3.12, Django 5.2.17, SQLite preview):

- 42 tests discovered; 39 passed, 3 SQL Server concurrency tests skipped on SQLite.
- Added exact-70 progression through all four stages and an existing-data policy-upgrade test.
- Existing tests cover private files, authorization, manual grading, revisions, re-locking, certificates, profiles and password reset.

The workflow now uses SQL Server 2022 with ODBC Driver 18 and mssql-django 2.0.0. The SQL Server job installs the driver, creates a database, runs migrations and seeding, then runs all tests including concurrent enrollment/submission/review. A successful run will be recorded below after verification.

The earlier MySQL run (37148168177) validated the previous edition only; it is not evidence of SQL Server compatibility. Public deployment and real SMTP configuration are not part of these tests.

## Verified SQL Server run

- Run: https://github.com/Radvinhz1/testsite/actions/runs/37204475262
- Application commit: `bf9764314a0ee36fb3bca3a6b0ffc992ba1357b1`.
- Python 3.13 + SQL Server 2022 + ODBC Driver 18: **all 42 tests passed**, including all three concurrency tests. Database creation, both migrations, sample seeding and model/migration consistency checks passed.
- Python 3.13 + SQLite: passed, with three database-specific concurrency tests intentionally skipped.
- Manual grading and exact-70 completion are covered by the successful test suite.

This last report update changes documentation only, not the tested application code.
