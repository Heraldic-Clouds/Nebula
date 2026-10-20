# Database migrations boundary

No migrations exist yet. Implement versioned PostgreSQL migrations, using the [data model](../../docs/architecture.md#data-model) and [ledger invariants](../../docs/billing.md#ledger-invariants).

Recommended implementation: SQLAlchemy plus Alembic, pinned when introduced. Add constraints and indexes alongside the first consuming feature. Test upgrade from a clean database and the previous supported revision, row-locking admission races, ledger balancing, unique payment/usage sources, and tenant isolation. Back up before production migrations; destructive schema changes require a reviewed data-retention decision.
