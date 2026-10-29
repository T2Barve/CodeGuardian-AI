# Corporate Security Policy: Database Security & Query Parameterization

**Policy ID:** SEC-002  
**Category:** SECURITY  
**Version:** 1.0.0  
**Effective Date:** 2026-01-01  
**Target Languages:** Python, SQL, TypeScript  

## 1. SQL Injection Prevention
All relational database interactions must use parameterized queries, prepared statements, or an approved Object-Relational Mapping (ORM) framework such as SQLAlchemy 2.0.
- Dynamic string formatting, f-strings, `%` interpolation, or string concatenation to build SQL statements is strictly prohibited.
- Always bind user inputs as query parameters using named placeholders.

## 2. Principle of Least Privilege
Database connections utilized by application microservices must operate under accounts with minimum required permissions.
- Administrative operations (DDL migrations) must be separated from runtime read/write workloads (DML).
- Direct access to `DROP TABLE`, `ALTER`, or administrative database roles is forbidden from public API services.

## 3. Database Connection Security and SSL
All database connections connecting to remote or cloud-hosted instances must enforce TLS/SSL encrypted transit (`sslmode=require` or `sslmode=verify-full`).
- Connection pooling limits must be explicitly bounded to prevent connection exhaustion.
