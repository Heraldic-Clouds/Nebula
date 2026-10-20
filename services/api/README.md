# Nebula backend boundary

Implementation is pending. Build a Python/FastAPI modular backend using the [architecture](../../docs/architecture.md) and [API contract](../../docs/product.md).

Planned modules: `auth`, `organizations`, `projects`, `catalog`, `instances`, `networks`, `ssh_keys`, `operations`, `openstack`, `billing`, `metering`, `assistant`, and `audit`. Keep HTTP routes thin; share authorization/admission services between UI and assistant actions. Run durable operation and metering workers as separate processes using PostgreSQL jobs/outbox.

Introduce pinned dependencies, migrations, Docker image, startup commands, and integration tests together. Do not add a fake OpenStack success path as the default runtime.
