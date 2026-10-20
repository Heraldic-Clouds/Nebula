# Nebula dashboard boundary

Implementation is pending. Build the React/TypeScript customer console against the real Nebula API using the [product design](../../docs/product.md).

Deliver account/project selection, instances, networks, SSH public keys, usage, billing, and PeopleWelcome chat incrementally. The server owns permissions, resource catalogs, rates, funds and confirmation records. Browser code must never receive Keystone application credentials, Stripe API keys, wallet credentials, or PeopleWelcome API secrets.

Provide responsive accessible layouts and honest pending/stale/failure states. The administration dashboard remains Horizon.
