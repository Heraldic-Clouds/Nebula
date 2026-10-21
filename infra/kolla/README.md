# Kolla-Ansible boundary

Implemented OpenStack 2026.1 globals, host preparation/preflight playbooks, a full-upstream-inventory renderer and gated deployment script for Keystone, Nova, Neutron, Glance, Placement and Horizon. See the [root README](../../README.md#threefold-provisioning-and-openstack) for executable commands. Linux/Kolla/live-node execution remains unverified on this Windows host.

`scripts/render_inventory.py` preserves the complete inventory shipped with the pinned upstream revision and replaces only host membership/variables. `scripts/deploy_openstack.py` stops on failed preflight, requires reboot persistence evidence and external-network qualification, and never provisions ThreeFold capacity. Ceph/Cinder are disabled.

KVM is the production goal. A separately opted-in QEMU/TCG inventory is development-only and must visibly report its performance limits. Do not guess external interfaces, public pools, or movable VIP support. Kolla-generated passwords and admin credentials stay outside Git.
