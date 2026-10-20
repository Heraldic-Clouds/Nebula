# Extension interfaces

Keep provider capabilities separate from customer API and billing policy. These are design interfaces, not implemented adapters or promised integrations.

| Interface | Intended responsibility |
| --- | --- |
| `InfrastructureProvisioner` | Operator-only ThreeFold node lifecycle; never callable directly from customer chat |
| `ComputeProvider` | Scoped catalog, create/delete/get/list/reconcile; initial implementation is OpenStack |
| `NetworkProvider` | Network/router/security group/public IP capabilities and operations |
| `UsageSource` | Normalized timestamped observations, lifecycle coverage, durable source identities |
| `PaymentProvider` | Verified external payment events and payment references; no direct arbitrary balance edits |
| `AssistantProvider` | Verified PeopleWelcome protocol, conversations and structured proposals |
| `StorageProvider` | Future object storage boundary, independent of OpenStack root disk metering |
| `ClusterProvisioner` | Future Kubernetes lifecycle built on authorized compute/network operations |

Every compute/network adapter reports a capability set, region/project context, provider IDs, idempotency/reconciliation behavior, and billable units. Unsupported features must be rejected explicitly, not silently emulated or routed to another provider.

Defer Akash GPUs, Golem, Storj, Kubernetes, Nebula GPU flavors, and Marco Polo coin payments. Hosting PeopleWelcome, Stratus-2, Amzy, and STAS is future workload/catalog work. Do not implement these integrations in the MVP. Additional ThreeFold nodes extend the existing provisioning path after compatibility and budget approval.
