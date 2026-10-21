# Database migrations boundary

Implemented Alembic migrations for customers, sessions, scoped projects, rates, durable operations, instances, usage, top-ups, webhook events and balanced journals. Database triggers enforce append-only ledger/usage/audit facts and immutable rate amounts. Run `nebula migrate` or the Compose migration service.

Migrations and transaction/concurrency behavior are tested on real PostgreSQL. Tests require `NEBULA_TEST_DATABASE_URL` and refuse to truncate any database whose name does not end in `_test`. Back up before production migrations; destructive schema changes require a reviewed data-retention decision.
