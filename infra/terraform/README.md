# ThreeFold Terraform boundary

Implemented Grid provider 1.11.6 resources for full-VM controller/compute hosts, persistent boot disks, a WireGuard network and sanitized inventory outputs. See the [root README](../../README.md#threefold-provisioning-and-openstack) for init/plan and explicitly approved saved-plan application.

The controller map accepts one or three entries; the compute map may be empty for an initial approved single-VM probe. Full cloud inventory generation requires at least one compute host. No real node IDs, image digest, wallet, quote or compatibility evidence has been supplied. Initialization and schema validation passed locally; no plan or apply ran.

Use operator-supplied secrets; never embed wallet mnemonics, WireGuard private keys, plans, or state in Git. Obtain explicit approval for the selected resources, quote and duration before any billable apply. No automatic purchase/apply workflow belongs in pull-request CI.
