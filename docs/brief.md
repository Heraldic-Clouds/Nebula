# Codex Prompt — Nebula Cloud MVP on ThreeFold

Build **Nebula**, an OpenStack-based public cloud deployed on decentralized ThreeFold infrastructure.

## 1. Infrastructure

Use:
- ThreeFold Grid for all infrastructure nodes
- Terraform (`threefoldtech/grid`) for provisioning
- Ubuntu 24.04 where supported
- OpenStack 2026.1 via Kolla-Ansible
- Docker for OpenStack services
- WireGuard for private node connectivity
- GitHub Actions for CI/CD

No AWS, Azure, GCP, or privately hosted infrastructure for the Nebula runtime.

## 2. Critical preflight

Before deploying OpenStack, provision a test ThreeFold VM and verify:

- SSH/root access
- `/dev/kvm` and CPU virtualization flags
- Nested KVM functionality
- Available CPU, RAM, disk and network interfaces
- Persistent storage
- VM-to-VM networking
- Public IPv4, ingress, floating IP and Neutron compatibility
- Required privileges for Open vSwitch, networking and virtualization

If KVM is unavailable, test whether Nova can operate using software emulation (QEMU/TCG), clearly label it development-only, and document severe performance limitations.

If networking or virtualization is unsupported, stop the affected deployment stage and report the blocker. Do not claim a functioning OpenStack cloud without successfully launching a tenant VM.

## 3. OpenStack MVP architecture

Provision ThreeFold nodes for:

**Controller**
- Keystone
- Glance
- Nova API/Scheduler
- Neutron services
- Placement
- Horizon
- MariaDB
- RabbitMQ

**Compute**
- Nova Compute
- libvirt/KVM if available
- QEMU fallback for testing only

**Networking**
- Neutron
- Private tenant networks
- Router/NAT
- Public ingress where ThreeFold allows it
- Security groups

Begin with the minimum viable node configuration, then provide Terraform definitions for scaling to three controller nodes.

Avoid Ceph in v1. Use supported persistent storage initially.

## 4. Nebula public cloud features

Implement a lightweight customer control panel with:

- Registration/login
- Customer organizations/projects
- VM creation/deletion
- Instance sizes
- Ubuntu VM images
- Network configuration
- SSH key management
- Instance status
- Usage dashboard
- Billing dashboard

Use OpenStack APIs rather than duplicating OpenStack's infrastructure logic.

Keep Horizon available as the administration dashboard.

## 5. Billing

Integrate Stripe with a prepaid customer balance and hourly usage metering.

Initial billable resources:
- vCPU-hours
- RAM GB-hours
- Storage GB-months
- Public IP-hours where applicable

Pricing must be configurable. Use whole-dollar prices where appropriate; do not introduce deceptive `.99` pricing.

Requirements:
- Stripe Checkout
- Verified webhooks
- Billing ledger
- Usage collection from OpenStack
- Customer invoices/receipts
- Quotas and spending limits
- Suspend new provisioning when funds are insufficient
- Idempotent charging and payment handling

Never grant paid entitlements based only on frontend payment confirmation.

## 6. PeopleWelcome AI Cloud Assistant

Integrate PeopleWelcome as Nebula's AI support and cloud administration interface.

Examples:
- "Create an Ubuntu VM with 4 CPUs and 8 GB RAM."
- "Why is my instance unreachable?"
- "Show my cloud usage."
- "Configure a private network."
- "Help me deploy Docker."

Architecture:

Customer → Nebula chat UI → PeopleWelcome LLM API → Nebula tool gateway → OpenStack API

Requirements:
- PeopleWelcome handles natural language and AI identity.
- Nebula owns infrastructure tools and permissions.
- Read-only troubleshooting is available by default.
- Destructive, billable or security-sensitive changes require explicit confirmation.
- Use scoped Keystone credentials.
- Log infrastructure actions.
- Never give the LLM unrestricted shell access or administrator credentials.

## 7. Future compatibility

Prepare modular interfaces for:

- Akash GPU capacity
- Additional ThreeFold nodes
- Golem compute
- Storj object storage
- Kubernetes cluster provisioning
- Nebula GPU instances
- Marco Polo coin payments
- Hosting PeopleWelcome, Stratus-2, Amzy and STAS

Do not implement these future integrations in this MVP.

## 8. Deployment and testing

Create:

- Terraform configuration
- Ansible/Kolla configuration
- Backend API
- Customer dashboard
- Database migrations
- Stripe integration
- PeopleWelcome assistant integration
- Docker development setup
- `.env.example`
- Deployment scripts
- Automated tests
- README with installation and operating instructions

Test end-to-end:

1. Provision ThreeFold infrastructure.
2. Deploy OpenStack.
3. Log in to Horizon.
4. Create a tenant network.
5. Launch an Ubuntu instance.
6. Confirm network connectivity.
7. Register a Nebula customer.
8. Add prepaid credit through Stripe test mode.
9. Provision a VM through Nebula.
10. Verify usage metering.
11. Ask PeopleWelcome to inspect the VM.
12. Delete the VM and stop metering.

Use test-mode payments until the complete metering and reconciliation process is validated.

## 9. Execution requirements

Inspect the repository first and reuse existing code.

Implement incrementally, not as disconnected mockups. Do not invent successful deployment results or undocumented ThreeFold capabilities.

Never commit wallet mnemonics, SSH private keys, Stripe secrets or OpenStack credentials.

Do not automatically purchase resources or run Terraform apply against billable ThreeFold infrastructure without explicit approval.

At completion, report:
- Implemented components
- Successfully tested components
- Deployment status
- ThreeFold compatibility findings
- Remaining blockers
- Estimated infrastructure cost based on actual selected nodes
- Commands to deploy and operate Nebula

**Success criterion:** A real ThreeFold-hosted OpenStack environment launches at least one customer VM, exposes it through the Nebula control panel, meters its usage, and supports PeopleWelcome AI assistance.