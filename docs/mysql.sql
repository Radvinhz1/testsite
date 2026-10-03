-- Run as a database administrator. This creates the database, not Django tables.
CREATE DATABASE IF NOT EXISTS testsite
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Create a dedicated user with your own password through MySQL Workbench or:
-- CREATE USER 'testsite'@'localhost' IDENTIFIED BY 'YOUR_UNIQUE_PASSWORD';
-- GRANT ALL PRIVILEGES ON testsite.* TO 'testsite'@'localhost';
-- Generate application tables with: python manage.py migrate
-- Test execution requires permission to create/drop a separate test_testsite database.
