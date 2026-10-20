# Deployment and operations plan

Status: future runbook. No Terraform configuration, deployment scripts, Kolla inventory, Docker Compose stack, or application binaries exist in this revision. Commands below are upstream command shapes for the implementation stage, not a working deployment from this checkout.

## Prerequisites and deployment order

1. Implement the preflight Terraform module and evidence tooling described in [infrastructure.md](infrastructure.md). Pin tools/provider versions and select verified image references.
2. Obtain actual candidate-node quotes and explicit approval for the exact billable resources, duration, and budget. Prepare a funded operator wallet, public SSH key, private state storage, and recovery access outside Git.
3. Provision the approved test VM; run the full compatibility gate. Provision an approved peer when needed for VM-to-VM tests. Record failures and stop affected stages.
4. After passing the gate and approving the cloud-node plan, provision the pilot controller/network and compute nodes with persistent disks and WireGuard access.
5. Generate a complete Kolla inventory and globals from actual interfaces, addresses, routes, storage, and validated public networking. Generate and store secrets privately.
6. Install the pinned Kolla-Ansible 2026.1 toolchain in an isolated operator environment. Install dependencies, bootstrap, precheck, deploy, and post-configure. Keep operator credentials private.
7. Validate Horizon, Keystone roles, image/flavor catalog, private tenant network, routing, security groups, and a real Ubuntu tenant VM before installing the customer-facing Nebula stack.
8. Build the implemented API/dashboard/worker containers, apply reviewed database migrations, configure Stripe test and verified PeopleWelcome credentials, and start the stack on ThreeFold.
9. Execute all acceptance steps and failure cases. Keep public customer admission and live payments disabled until results pass review.

## Terraform command shapes

Run these only after real Terraform resources have been implemented in the chosen environment directory. `init` downloads providers and `plan` can query providers; keep credentials and resulting artifacts private. An apply creates billable contracts and needs the approval described above.

```bash
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=approved.tfplan
# Stop here until the exact plan, resources, and spend have explicit approval.
terraform apply approved.tfplan
```

Save the approved plan securely and apply that plan without silently changing variables. Never upload state/plan JSON as a public CI artifact. Destroying an infrastructure deployment can delete all tenant data; cleanup needs an explicit resource list and preserved-data decision.

## Kolla command shapes

After installing the pinned toolchain and preparing its complete `multinode` inventory, `/etc/kolla/globals.yml`, secrets, and endpoint configuration:

```bash
kolla-ansible install-deps
kolla-ansible bootstrap-servers -i ./multinode
kolla-ansible prechecks -i ./multinode
kolla-ansible deploy -i ./multinode
kolla-ansible post-deploy -i ./multinode
```

These commands change host state. They must run only against the verified, approved pilot inventory. Follow the upstream [2026.1 deployment guide](https://docs.openstack.org/kolla-ansible/2026.1/user/quickstart.html) and resolve failures before continuing. Do not run a convenience demo initialization script against a customer cloud without reviewing the resources it creates.

## Planned development interface

The implementation should provide Docker Compose services for `api`, `worker`, `metering`, `dashboard`, and `postgres`, plus a migration task. A development adapter may use deterministic fixtures for API tests, but the UI must identify fixture mode and no fixture may satisfy live acceptance. The actual Compose file, Dockerfiles, application installation/start commands, and scripts are roadmap deliverables; they are not available yet.

The future backend CLI should expose migrations, a single metering/reconciliation run, an operator-approved rate-card import, and health diagnostics. Define and test their exact command names when implementation lands rather than publishing non-existent commands as operational instructions.

## End-to-end acceptance run

Every step is currently **not run**. Record the commit, operator, UTC timestamp, exact configuration, sanitized output, and referenced IDs. Keep secrets and raw tenant data outside Git.

| Step | Action | Required evidence |
| --- | --- | --- |
| 1 | Provision approved ThreeFold infrastructure | Actual node IDs, contract IDs, sizing, quote/approval, compatibility report |
| 2 | Deploy OpenStack | Passing Kolla prechecks/deploy and healthy required services |
| 3 | Log in to Horizon | Operator login and matching project/service inventory |
| 4 | Create a tenant network | Network, subnet, router, DHCP/metadata and security-group verification |
| 5 | Launch an Ubuntu instance | Actual Nova server ID, successful guest boot, expected flavor/image |
| 6 | Confirm connectivity | Guest SSH, outbound access, approved inbound path and denied unauthorized traffic |
| 7 | Register a Nebula customer | Verified account, organization, role and isolated Keystone project mapping |
| 8 | Add prepaid credit in Stripe test mode | Checkout/session/event IDs, verified paid webhook, exactly one credit journal |
| 9 | Provision through Nebula | Customer request, confirmation, operation ID, actual VM visible in dashboard |
| 10 | Verify hourly metering | Observed lifecycle, rated units, applied rates, idempotent debit and correct balance |
| 11 | Ask PeopleWelcome to inspect the VM | Real API response and scoped read-only tool audit; no simulated assistant |
| 12 | Delete the VM and stop its metering | Actual deletion, final interval, no later VM charges; separately accounted retained storage/IPs |

Passing requires a ThreeFold-hosted OpenStack customer VM managed through Nebula, metered against prepaid credit, and inspected through PeopleWelcome. A dashboard screenshot, successful container startup, or mocked integration does not pass the run.

## Verification by layer

- Infrastructure: Terraform formatting/schema validation, generated inventory checks, preflight stop behavior, actual host and nested guest tests, networking, persistence, and recovery.
- Backend: membership/tenant isolation, session/CSRF controls, quotas, balance reservation races, durable jobs, OpenStack timeout recovery, and resource reconciliation.
- Billing: real PostgreSQL transactions, Stripe sandbox Checkout, signature failures, delayed/duplicate/out-of-order events, refunds, rate boundaries, rounding, short-lived VMs, collector downtime, final deletion settlement.
- Assistant: real provider protocol test, read-only tools, permission denial, injection resistance, explicit confirmation, replay protection, redaction.
- Dashboard: primary flows, accessibility, mobile layout, empty/stale/error states, launch estimates, delayed credit, destructive confirmations, status updates.
- CI: pinned dependencies, application build/checks, migration checks, credential-free unit/integration tests, container builds, and configuration validation. Deployment and payment tests use isolated protected environments.

## Operating runbooks to implement

| Signal | Initial response |
| --- | --- |
| Stale metering or usage gap | Freeze new billable admission, inspect collector/coverage watermark, recover evidence and reconcile |
| Payment pending | Inspect verified event inbox and Stripe session status; do not manually credit from a screenshot |
| Ledger mismatch | Freeze affected billing admission, compare immutable journals and projections, use audited adjustment only |
| Stuck VM operation | Inspect operation/job lease, search provider correlation IDs before retry, reconcile leaked resources |
| Low operator wallet balance | Alert operators and top up through an authorized process before ThreeFold contract availability is affected |
| Host/OVS failure | Preserve logs, isolate affected service, verify tenant impact and documented recovery path |
| PeopleWelcome outage | Show unavailability; direct authorized users to dashboard flows while retaining audit |
| Credential exposure | Revoke/rotate credentials, invalidate affected sessions, inspect audit and sanitize artifacts |

Monitor control-plane health, host/storage capacity, job backlog, error rate, latency, metering freshness, webhook lag, balance drift, backups, TLS expiry, and operator wallet funding. Define thresholds from measured pilot behavior.

Back up PostgreSQL, required OpenStack state, image catalog, configuration, and credential recovery material to approved ThreeFold-hosted storage. Encrypt backups, record retention, and prove restore on an isolated environment. No RPO/RTO, automatic failover, or disaster recovery guarantee is claimed before these tests.
