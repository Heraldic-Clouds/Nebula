# Kolla-Ansible boundary

No inventory, playbook, or globals configuration is implemented yet. Target OpenStack 2026.1 in Docker on supported Ubuntu 24.04 ThreeFold VMs, following the [infrastructure gates](../../docs/infrastructure.md) and [deployment sequence](../../docs/operations.md).

Begin with the complete upstream multinode inventory for the pinned release. Generate node/interface values from real Terraform outputs and preflight evidence. Include controller/network roles, compute, required service groups, private endpoints and qualified persistent storage; avoid Ceph in v1.

KVM is the production goal. A separately opted-in QEMU/TCG inventory is development-only and must visibly report its performance limits. Do not guess external interfaces, public pools, or movable VIP support. Kolla-generated passwords and admin credentials stay outside Git.
