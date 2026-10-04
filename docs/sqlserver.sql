-- Run in SSMS as a database administrator, connected to your intended instance.
USE [master];
GO
IF DB_ID(N'testsite') IS NULL
    CREATE DATABASE [testsite] COLLATE Latin1_General_100_CI_AS_SC;
GO
-- Django uses NVARCHAR for Unicode text; Persian is supported.
-- Windows Authentication: grant access to the Windows account running Django.
-- Example ONLY: replace MACHINE\YourUser with your actual account.
-- CREATE LOGIN [MACHINE\YourUser] FROM WINDOWS;
-- USE [testsite];
-- CREATE USER [MACHINE\YourUser] FOR LOGIN [MACHINE\YourUser];
-- ALTER ROLE db_owner ADD MEMBER [MACHINE\YourUser];
-- db_owner is convenient for LOCAL setup/migrations, not the production web account.

-- Alternative: SQL Authentication (requires Mixed Mode enabled on SQL Server).
-- CREATE LOGIN [testsite_app] WITH PASSWORD = N'REPLACE_WITH_YOUR_OWN_STRONG_PASSWORD';
-- USE [testsite];
-- CREATE USER [testsite_app] FOR LOGIN [testsite_app];
-- ALTER ROLE db_datareader ADD MEMBER [testsite_app];
-- ALTER ROLE db_datawriter ADD MEMBER [testsite_app];
-- GRANT VIEW DEFINITION TO [testsite_app];
-- Use a separate migration account with schema modification privileges.
-- Application tables are created by: python manage.py migrate
-- Test account needs permission to create/drop test_testsite; never use production data.
