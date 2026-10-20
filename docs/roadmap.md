# MVP delivery roadmap

This revision completes the initial repository setup and design. All implementation/deployment milestones below remain pending. Deliver connected increments and update the README only when evidence supports the new status.

## Milestone 0: repository and design

- [x] Preserve the existing license and repository history.
- [x] Record the original brief and product definition.
- [x] Define service boundaries, tenant model, API, billing, and assistant security.
- [x] Define compatibility gates, deployment evidence, operating plan, and future extension boundaries.
- [x] Provide a credential-free environment template and secret/state ignore rules.

Completion of this milestone does not implement the cloud runtime.

## Milestone 1: compatibility and provider qualification

- [ ] Implement pinned Terraform preflight configuration, outputs and operator-run scripts.
- [ ] Choose candidate node IDs, verified full-VM image, disk configuration, and provider version.
- [ ] Capture actual quote and obtain explicit approval before billable provisioning.
- [ ] Prove SSH/root access, resource inventory, nested KVM, required network privileges, persistence, and VM-to-VM connectivity.
- [ ] If needed, isolate and measure development-only Nova QEMU/TCG; do not promote it as production KVM.
- [ ] Prove the Neutron external routing/ingress model, overlay transport and MTU.
- [ ] Publish a sanitized capability report with passed/failed/unsupported results and stop rules.

Exit: evidence supports an OpenStack pilot on selected ThreeFold capacity, or the affected stage is explicitly blocked. Do not substitute another runtime cloud to make the demonstration pass.

## Milestone 2: OpenStack pilot and development skeleton

- [ ] Implement node maps for one controller plus compute, and a three-controller topology configuration.
- [ ] Generate complete Kolla inventory/globals and implement safe deployment/precheck wrappers.
- [ ] Deploy OpenStack 2026.1 services with qualified persistent storage; exclude Ceph.
- [ ] Verify Horizon, approved Ubuntu image checksums, flavors, tenant network, guest boot and connectivity.
- [ ] Add FastAPI and React/TypeScript projects with pinned dependencies.
- [ ] Add Dockerfiles, Docker Compose development stack, PostgreSQL, migrations, jobs/outbox and health checks.
- [ ] Add GitHub Actions for credential-free checks/builds and separate protected deployment workflows.

Exit: a real Ubuntu guest works on ThreeFold-hosted OpenStack, and local development can run the connected Nebula stack with an explicitly identified adapter configuration.

## Milestone 3: accounts, projects and resource workflows

- [ ] Implement registration/login, verification/reset delivery, secure sessions, CSRF and rate limits.
- [ ] Implement organization roles, invitations, project membership and Keystone onboarding.
- [ ] Implement project-scoped credential storage and an OpenStack SDK adapter.
- [ ] Implement image/flavor catalog, quotas, public SSH key management and network configuration.
- [ ] Implement durable create/delete operations with confirmation, idempotency, timeout recovery and reconciliation.
- [ ] Build the customer dashboard against the real API; keep Horizon available to operators.
- [ ] Prove cross-tenant isolation and reject manipulated provider IDs/roles.

Exit: an authenticated customer sees and operates only authorized project resources. Billable admission stays disabled until the prepaid billing gate is complete.

## Milestone 4: prepaid billing

- [ ] Implement immutable versioned rates, fixed-point ledger, reservations and transaction constraints.
- [ ] Add Stripe sandbox Checkout, restricted keys, verified webhook inbox and session-level fulfillment idempotency.
- [ ] Collect real OpenStack lifecycle/resource usage, including short-lived and out-of-band resources.
- [ ] Implement hourly settlement, deletion boundaries, rate changes, rounding carry and reconciliation.
- [ ] Implement top-up receipts/invoice references, usage statements, balance/limits dashboard and notifications.
- [ ] Block new provisioning when credit, quota, spend allowance or metering safety fails.
- [ ] Test delayed/duplicate/out-of-order payments, concurrency, refunds/disputes, gaps and final settlement.

Exit: a sandbox-funded customer can launch a real VM, see correct metered debit, delete it, and see the VM's charging stop at the final settled boundary. Keep live payments disabled.

## Milestone 5: PeopleWelcome assistant

- [ ] Obtain and verify the real PeopleWelcome API endpoint, authentication, schema, model selection and data policy.
- [ ] Implement the provider adapter and strict allowlisted tool gateway.
- [ ] Deliver read-only instance/network/usage diagnostics with project-scoped access.
- [ ] Add server-owned, expiring, single-use confirmations for every billable/destructive/security-sensitive change.
- [ ] Add infrastructure action audit and test prompt injection, forged approvals and credential redaction.
- [ ] Verify a real PeopleWelcome conversation that inspects the acceptance VM.

Exit: assistant output is based on real, authorized observations; confirmed actions pass through the same admission and job paths as the dashboard.

## Milestone 6: release validation and scale preparation

- [ ] Pass all twelve acceptance steps in [operations.md](operations.md#end-to-end-acceptance-run).
- [ ] Complete backups/restores, monitoring, operator wallet alerts, incident/cleanup procedures and capacity benchmarks.
- [ ] Resolve public tax/invoice terms, account abuse controls, privacy/retention and overspend policies.
- [ ] Test three-controller quorum/failover and endpoint reachability before claiming HA.
- [ ] Provide exact installed commands and sanitized results for the final implementation.
- [ ] Review metering/payment reconciliation before a separate decision to enable live payments.

## Requirements traceability

| Original brief section | Design location | Implementation / verification milestone |
| --- | --- | --- |
| 1. ThreeFold, Terraform, Ubuntu, OpenStack, Docker, WireGuard, GitHub Actions | [Infrastructure](infrastructure.md), [architecture](architecture.md) | M1-M2; runtime restrictions apply throughout |
| 2. Critical preflight, KVM, QEMU limitations, networking blockers | [Compatibility gate](infrastructure.md#critical-compatibility-gate) | M1 live evidence; M2 Nova guest proof |
| 3. Controller, compute, Neutron, minimal nodes, three controllers, no Ceph | [Topology/storage](infrastructure.md) | M2 pilot; M6 HA qualification |
| 4. Accounts, projects, VM lifecycle, sizes/images, networks, keys, status, usage/billing dashboard | [Product/API](product.md) | M3 customer workflows; M4 usage/billing |
| 5. Stripe, prepaid balance, hourly usage, ledger, receipts, quotas, limits, idempotency | [Billing](billing.md) | M4 sandbox integration and concurrency tests |
| 6. PeopleWelcome, gateway, scoped access, confirmation, audit, no unrestricted shell | [Assistant/security](assistant-security.md) | M5 real provider and permission tests |
| 7. Future providers, GPUs, Kubernetes, coin payments and hosted applications | [Extension boundaries](../extensions/README.md) | Interfaces only; integrations deferred |
| 8. Terraform/Kolla/backend/dashboard/migrations/Stripe/assistant/Docker/env/scripts/tests/README | [Component directories](../README.md#repository), [operations](operations.md) | Environment/README design done; runnable artifacts M1-M5 |
| 8. Twelve-step end-to-end test | [Acceptance run](operations.md#end-to-end-acceptance-run) | M6, with earlier component evidence |
| 9. Reuse repository, incremental work, no fake claims, no secrets, approval before spend | [Contributing](../CONTRIBUTING.md), [operations](operations.md) | Continuous; preserved existing license/history |
| 9. Completion report and actual node costs | [Cost worksheet](infrastructure.md#cost-worksheet), status report below | Populate from real deployment; currently unverified/unquoted |

## Current completion report

| Requested report field | Current result |
| --- | --- |
| Implemented components | Project structure, README, design/operating documents and environment template; no runtime services |
| Successfully tested components | Repository/documentation integrity checks only; no application or cloud tests can run yet |
| Deployment status | Not deployed; no resources purchased |
| ThreeFold compatibility | Not tested on live nodes; nested KVM, storage and Neutron remain open gates |
| Remaining blockers | Implementation, approved nodes/budget, real compatibility evidence, operator credentials, Stripe sandbox configuration, verified PeopleWelcome contract, email delivery and operational policies |
| Infrastructure cost | Unquoted; no actual nodes selected |
| Commands | Current repository commands in README; upstream future command shapes in operations, exact application commands pending implementation |

## Deferred integrations

Akash GPU capacity, Golem, Storj, Kubernetes clusters, Nebula GPU instances, Marco Polo payments, and hosted PeopleWelcome/Stratus-2/Amzy/STAS services remain out of scope for v1. Adding ThreeFold compute nodes is the first capacity expansion path. Do not build speculative provider logic before the initial acceptance run works.
