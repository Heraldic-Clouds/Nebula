# Nebula

**An OpenStack cloud platform powered by decentralized, blockchain-coordinated compute on the ThreeFold Grid.**

Nebula brings familiar cloud workflows to distributed infrastructure: create an account, fund a prepaid balance, launch an Ubuntu virtual machine, configure its network, and manage it through a customer dashboard or the PeopleWelcome cloud assistant.

OpenStack manages customer infrastructure. ThreeFold supplies the underlying capacity, with TFChain coordinating infrastructure identities and deployment contracts. Nebula connects those layers through a customer API, usage ledger, and permission-controlled tools. Customer workloads run on compute nodes, not on a blockchain.

## Project status

**Pilot implementation. No live ThreeFold/OpenStack cloud has been deployed or verified.**

The repository now includes pinned ThreeFold Terraform resources, Kolla-Ansible deployment wrappers, automated Linux preflight checks, a FastAPI/OpenStack backend, a React dashboard, PostgreSQL migrations, durable VM operations, Stripe test Checkout/webhooks, hourly usage settlement, a read-only PeopleWelcome adapter, Docker Compose, and automated tests. The existing architecture documents remain the design reference; source code and the commands below describe the implemented pilot.

Locally verified: Terraform provider initialization/schema validation, dashboard production build, PostgreSQL migrations and transaction tests, API/login/tenant-isolation checks, billing idempotency/concurrency, Stripe signature verification, worker lifecycle tests, and browser login/error states. Provider responses in automated tests are explicitly test doubles; no sandbox payment, live VM, or live AI response is claimed.

ThreeFold nested KVM, persistent disks, required network privileges, and Neutron external networking remain unverified. A successful OpenStack installation alone does not meet the MVP acceptance criteria: Nebula must launch and connect to a real customer VM, meter it, and inspect it through PeopleWelcome.

## The MVP

| Area | Intended behavior |
| --- | --- |
| Accounts | Registration, login, organizations, memberships, and project isolation |
| Compute | Create/delete Ubuntu VMs, choose instance sizes, view status and operations |
| Networking | Private tenant networks, router/NAT, security groups, and supported public ingress |
| SSH keys | Register public keys and select one at launch; never upload private keys |
| Usage | vCPU-hours, RAM GB-hours, storage GB-months, and applicable public IP-hours |
| Billing | Stripe Checkout top-ups, verified webhooks, prepaid ledger, receipts, quotas, and spending limits |
| Assistant | PeopleWelcome chat with read-only diagnostics and explicitly confirmed infrastructure changes |
| Administration | Horizon for operators; scoped customer access through Nebula |

## Architecture

```mermaid
flowchart TB
    Customer[Customer] --> UI[Nebula customer dashboard]
    UI --> API[Nebula API and authorization]
    API --> DB[(PostgreSQL: accounts, ledger, jobs, audit)]
    API --> Checkout[Stripe Checkout: prepaid top-ups]
    Checkout --> Webhooks[Verified webhook inbox]
    Webhooks --> DB
    API --> Jobs[Durable job and reconciliation workers]
    Jobs --> OS[OpenStack APIs]
    OS --> Controller[Controller and network services]
    OS --> Compute[Nova compute and libvirt]
    Compute --> VMs[Customer Ubuntu VMs]
    Meter[Usage collector and rating worker] --> OS
    Meter --> DB
    UI --> Chat[PeopleWelcome adapter]
    Chat --> LLM[PeopleWelcome LLM API]
    Chat --> Gateway[Nebula tool gateway and confirmations]
    Gateway --> API
    Operator[Operator] --> Horizon[Horizon admin dashboard]
    Horizon --> OS
    Terraform[Terraform: threefoldtech/grid] --> Grid[ThreeFold capacity and WireGuard network]
    Grid --> Controller
    Grid --> Compute
    Terraform --> Chain[TFChain deployment contracts]
```

The production runtime, including Nebula's API, database, workers, dashboard hosting, and OpenStack nodes, is intended to reside on ThreeFold. Stripe and PeopleWelcome are external APIs required by the brief. GitHub hosts source and CI; CI must not become the runtime. No AWS, Azure, GCP, or privately hosted runtime is part of this design.

## Technology

| Layer | Design choice |
| --- | --- |
| Infrastructure | ThreeFold Grid, Terraform provider `threefoldtech/grid`, WireGuard |
| Host and cloud | Ubuntu 24.04 where supported; OpenStack 2026.1, Kolla-Ansible, Docker |
| Customer dashboard | React and TypeScript, served behind a same-origin TLS reverse proxy |
| Backend | Python/FastAPI with a server-side OpenStack SDK adapter |
| Persistence | PostgreSQL, versioned migrations, transactional jobs/outbox |
| Payments | Stripe-hosted Checkout in a sandbox/test environment; Nebula prepaid ledger |
| Assistant | PeopleWelcome adapter, server-side tool gateway, scoped Keystone credentials |
| Delivery | GitHub Actions for checks; operator-approved infrastructure changes |

Application dependencies are pinned in `pyproject.toml` and the dashboard lock file. Terraform pins Grid provider 1.11.6; Kolla dependencies pin an exact upstream 2026.1 revision. No infrastructure deployment or Terraform apply runs in CI.

## Repository

```text
nebula/
  README.md                    Project overview and current status
  LICENSE                      Existing MIT license
  .env.example                 Empty configuration contract; no credentials
  docs/
    brief.md                   Original supplied requirements
    architecture.md            Services, trust boundaries, data model, and jobs
    product.md                 Dashboard, workflows, API, and roles
    billing.md                 Prepaid ledger, metering, and reconciliation
    assistant-security.md      PeopleWelcome tools and security controls
    infrastructure.md          ThreeFold topology and compatibility gates
    operations.md              Deployment sequence, evidence, and runbooks
    roadmap.md                 Milestones and requirements traceability
    sources.md                 Primary references and verification limits
  services/api/                Backend implementation boundary
  apps/dashboard/              Customer dashboard implementation boundary
  db/migrations/               Database migration boundary
  infra/terraform/             ThreeFold provisioning boundary
  infra/kolla/                 Ansible/Kolla deployment boundary
  extensions/                  Future provider interfaces
```

## Get started

Requires Python 3.12+, Node 24/pnpm 10.11, Docker Engine/Compose, and Terraform 1.7+. Kolla must run on Linux. From this checkout:

```bash
python -m pip install -e '.[test]'
nebula init-env
docker compose up --build -d
docker compose exec api nebula create-customer --email customer@example.com
```

`init-env` creates a private `.env` with a fresh encryption key and database password without printing them. The account command prompts for a password and grants neither credit nor provider access. Open `http://localhost:8080`. Public deployment must use the TLS overlay, `NEBULA_COOKIE_SECURE=true`, a valid HTTPS `NEBULA_PUBLIC_URL`, and real certificate/key paths:

```bash
python scripts/deploy_app.py --production
```

Run that command on approved ThreeFold capacity, not another hosting provider. The initial private pilot may share the controller; public service needs the isolation and operational qualification specified in the existing design.

### ThreeFold provisioning and OpenStack

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
# Supply actual selected node IDs, verified Ubuntu full-VM flist/checksum and public SSH key.
# Export TF_VAR_mnemonic privately. No actual nodes/image checksum were selected by this task.
terraform -chdir=infra/terraform plan -var-file=pilot.tfvars -out=approved.tfplan
```

Do not apply until the selected nodes, actual quote, duration and exact plan have explicit approval. The apply wrapper requires the saved plan's SHA-256 plus the approval/budget reference:

```bash
python scripts/terraform_apply.py infra/terraform/approved.tfplan --approve-plan-sha256 APPROVED_DIGEST --approved-budget 'APPROVAL_REFERENCE_AND_BUDGET'
mkdir -p .runtime
terraform -chdir=infra/terraform output -json hosts > .runtime/hosts.json
```

Connect the operator's WireGuard interface using the sensitive `wireguard_config` output, keeping it out of logs/Git. In a Linux virtual environment, install `infra/kolla/requirements.txt`. Render the **complete installed upstream inventory** with real interface names:

```bash
python scripts/render_inventory.py --hosts .runtime/hosts.json --template .venv-kolla/share/kolla-ansible/ansible/inventory/multinode --management-interface VERIFIED_INTERFACE --external-interface VERIFIED_EXTERNAL_INTERFACE --private-key ~/.ssh/nebula
python scripts/deploy_openstack.py prepare
python scripts/deploy_openstack.py write-marker
# write-marker deliberately fails with PERSISTENCE_PENDING until a reboot proves persistence.
python scripts/deploy_openstack.py reboot
python scripts/deploy_openstack.py preflight
python scripts/deploy_openstack.py deploy --external-network-evidence .runtime/external-network-evidence.json
```

The external-network evidence JSON must contain `approved_by`, `approved_at`, `provider_subnet`, `return_route`, `recovery_access`, and the generated inventory's `inventory_sha256`. This is an explicit operator qualification gate, not automatic proof of Neutron support. `--transport-mtu` configures the measured private transport MTU. Use `--development-tcg` only for an isolated development experiment; it never silently replaces KVM. Three-controller inventories require a separately qualified HA endpoint.

After Kolla deployment, use `python scripts/openstack_smoke.py --help` for the actual guest boot/SSH/connectivity test. It requires explicit `--approve-guest-create`, an existing tenant network, image, flavor and SSH key. It supplies a fresh guest SSH host key through cloud-init and pins that key for strict host verification. It removes its test VM afterward and records the provider ID even if cleanup fails. Horizon success alone does not pass this test.

### Bind a customer and enable the pilot

On the operator host, `scripts/bootstrap_customer.py` creates a Keystone customer/project, private subnet/router, an explicitly scoped SSH ingress rule and a scoped application credential. Supply approved existing image/flavor/external-network IDs, a trusted `--ssh-cidr`, a private `.runtime/customer` output directory, and `--approve-project-create`. It creates no VM or public IP.

```bash
python scripts/bootstrap_customer.py --help
docker compose cp .runtime/customer/catalog.json api:/tmp/customer-catalog.json
cat .runtime/customer/credentials.json | docker compose exec -T api nebula bind-project --email customer@example.com --catalog /tmp/customer-catalog.json --credentials-stdin
# Example TEST rates in micro-USD; choose operator-approved rates before offering service.
docker compose exec api nebula rates --cpu-micro-usd 10000 --ram-gb-micro-usd 1000 --storage-gb-month-micro-usd 100000
docker compose exec worker nebula-worker --once
```

The binding command verifies live Keystone scope and the catalog before encrypting the credentials in PostgreSQL. Use a verified Ubuntu image; no image download/checksum is fabricated. The dashboard can add customer SSH public keys. Initial quotas and lifetime spending limits are configurable. Set `NEBULA_PROVISIONING_ENABLED=true` and recreate API/worker containers only after infrastructure approval, a passing smoke test, rates, credit and fresh collection.

### Stripe and PeopleWelcome

Set `NEBULA_STRIPE_API_KEY` to a restricted sandbox/test key and `NEBULA_STRIPE_WEBHOOK_SECRET` to the endpoint/CLI signing secret. Forward `checkout.session.completed` and `checkout.session.async_payment_succeeded` to `/api/v1/webhooks/stripe`; when the Stripe CLI is available:

```bash
stripe listen --events checkout.session.completed,checkout.session.async_payment_succeeded --forward-to localhost:8080/api/v1/webhooks/stripe
```

Checkout grants credit only from verified, paid, amount/currency/ownership-matched sessions. Browser redirects grant none. Live keys/events are rejected. Settlement covers observed Nebula-managed CPU, RAM and root-disk allocations hourly and conservatively through the last confirmed presence at deletion. Unattached volumes/IPs, refunds/disputes, and notification-based exact lifecycle accounting are not implemented; this is not ready for live-money billing. Unknown provider resources or out-of-band resize block new admission.

PeopleWelcome now uses the native v5 character/conversation API documented at [the developer page](https://peopl.ewelco.me/developer). It is **not** an OpenAI Chat Completions endpoint: authentication uses a ZITADEL access token, character `model=openai` selects the provider, and PeopleWelcome's server selects its configured OpenAI model (documented default **`gpt-6-luna`**). Nebula cannot force a literal model name in a chat request.

After updating an existing installation, set the two PeopleWelcome origins from `.env.example` (remove any old Chat Completions URL), then run `docker compose build`, `docker compose run --rm migrate`, and `docker compose up -d`. Sign into Nebula, open **PeopleWelcome**, enter your authorized PeopleWelcome access token, and select an active OpenAI character you own. Tokens are encrypted server-side and never returned to the browser. Renew expired access with the same account. One PeopleWelcome account is permanently bound to one Nebula customer, even after disconnect, to keep remote conversation histories isolated. No shared API token or direct OpenAI key is used. One-click OAuth sign-in requires a separately registered Nebula redirect/client; this release accepts an already-authorized token rather than reusing PeopleWelcome's frontend OAuth client.

Support sends only the customer's message and a bounded project snapshot (VM status/configuration/freshness, prepaid balance and settled usage). It never sends Keystone credentials, SSH keys or connection tokens as message context. `train_memory=false` is always sent. Character history remains in the customer's PeopleWelcome account. The documented API has no function-calling contract, so the adapter has no executable tools; confirmed VM actions remain in the dashboard.

Chat submissions are durable and idempotent: `POST /api/v1/assistant/messages` requires `Idempotency-Key`, returns a local turn ID, and queues `/api/v1/agent/chat`. `GET /api/v1/assistant/messages/{id}` polls the upstream job at most every two seconds and reads new conversation replies after completion or failure. A timeout preserves the exact submitted payload/key; `POST /api/v1/assistant/messages/{id}/resume` resumes the same request. The dashboard recovers pending turns after reload, respects rate-limit backoff and shows partial replies on failure. Replies are from the connected conversation, which may also be used directly in PeopleWelcome; media jobs do not block text.

The developer page, public provider status and OIDC discovery were reachable during verification. `/openapi.json` returned 403. Authenticated submit/poll/reply behavior is tested against explicit HTTP test doubles and a real disposable PostgreSQL database; **live authenticated chat has not been verified without a customer token and active character**. No resource provisioning is needed to connect support.

### Checks and operation

```bash
# Must be a disposable PostgreSQL database with a name ending in _test.
NEBULA_TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost/nebula_test python -m pytest -q
pnpm --dir apps/dashboard install --frozen-lockfile
pnpm --dir apps/dashboard build
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform validate
docker compose logs --tail=100 api worker
docker compose exec worker nebula-worker --once
docker compose exec api nebula reconcile-operation OPERATION_ID
```

Ambiguous creates require operator reconciliation and never blindly repeat a Nova create. Operation failures keep conservative reservations until the actual remote allocation is resolved/deleted. Registration, multi-member organizations, refunds, exact notification-based metering, and assistant mutation confirmations remain outside this minimum pilot. No new planning documents replace the original architecture.

## Deployment gates

1. Select candidate ThreeFold nodes and obtain an actual quote. Approve the exact billable test deployment before applying Terraform.
2. Provision a test VM and verify root/SSH access, CPU flags, `/dev/kvm`, an actual nested guest, storage persistence, network interfaces, and necessary privileges.
3. Verify VM-to-VM connectivity, tenant overlay MTU, router/NAT, public ingress, and the external routing/allocation model needed by Neutron.
4. If KVM is unavailable, permit an explicitly opted-in QEMU/TCG development experiment only. Its performance is severely limited; it is not a production compute tier.
5. Stop the affected stage if virtualization or networking is unsupported. Record the blocker rather than replacing the required runtime with another cloud.
6. Deploy OpenStack and complete the twelve-step [acceptance run](docs/operations.md#end-to-end-acceptance-run).

Never purchase resources or run a billable `terraform apply` without explicit approval. Keep payments in test mode until metering and reconciliation are validated. Never grant balance from a browser success redirect.

## Cost and compatibility

**No nodes have been selected, no capacity has been purchased, and no infrastructure cost has been quoted.** The cost worksheet and required compatibility evidence are in [infrastructure.md](docs/infrastructure.md). Example sizing is a planning target, not an available-node claim or price estimate.

Kolla-Ansible's [2026.1 support matrix](https://docs.openstack.org/kolla-ansible/2026.1/user/support-matrix) lists Ubuntu 24.04. This supports the host OS choice; it does not prove ThreeFold can host nested OpenStack. See [sources and open questions](docs/sources.md).

## Future compatibility

Keep adapters available for Akash GPU capacity, Golem compute, Storj object storage, Kubernetes provisioning, GPU instances, Marco Polo coin payments, and hosting PeopleWelcome, Stratus-2, Amzy, and STAS. These are future integrations and are not implemented in the MVP. Additional ThreeFold nodes use the same provisioning boundary.

## Contributing and license

Read [CONTRIBUTING.md](CONTRIBUTING.md) before implementing a component. Record evidence for deployment claims, preserve tenant isolation, and keep credentials out of Git, logs, browser bundles, and AI prompts.

Maintainer identity for this repository: **TantalusDenton** (`thomasdxdenton@hotmail.com`). Licensed under the existing [MIT license](LICENSE).
