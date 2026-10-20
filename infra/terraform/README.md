# ThreeFold Terraform boundary

No Terraform resources are implemented yet. Use only the `threefoldtech/grid` provider for the required runtime. Follow the [infrastructure design](../../docs/infrastructure.md).

Deliver a minimal preflight environment first, then a cloud-node environment accepting stable controller/compute maps. Support one controller initially and a three-controller configuration for qualified expansion. Pin the provider and image references, commit the dependency lock file, and generate only sanitized inventory inputs.

Use operator-supplied secrets; never embed wallet mnemonics, WireGuard private keys, plans, or state in Git. Obtain explicit approval for the selected resources, quote and duration before any billable apply. No automatic purchase/apply workflow belongs in pull-request CI.
