# Nebula backend boundary

Implemented in `nebula/`: FastAPI sessions/CSRF, encrypted project credentials, real OpenStack SDK operations, PostgreSQL-backed worker, prepaid Stripe test credit, usage settlement and read-only PeopleWelcome support. See the [root README](../../README.md#get-started) for executable setup/binding/operation commands.

This minimum pilot uses one operator-created customer and scoped Keystone project per account. Public registration and multi-member organizations remain unimplemented. The worker runs separately with `nebula-worker`; no mock provider is installed in runtime code.

Tests live under `tests/` and use real PostgreSQL with explicitly isolated provider doubles. No live OpenStack or PeopleWelcome verification has run without credentials.
