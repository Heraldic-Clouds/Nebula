# Customer product and API design

Status: contract for implementation; none of these routes is served yet.

## Dashboard

Use a clear cloud console with a project selector, persistent navigation, and visible credit/usage status. Use a restrained dark navy and neutral interface with cyan accents, readable tables, and explicit warning/error states. Do not use color as the only status indicator. Support keyboard operation, labeled forms, accessible dialogs, and reduced motion.

| View | Primary content and action |
| --- | --- |
| Sign up / sign in | Registration, email verification, login, password reset, session expiry |
| Overview | Credit, current burn estimate, spending limit, active VMs, unresolved operations, data freshness |
| Organizations and projects | Memberships, role changes, invitations, project selection, quotas |
| Instances | Searchable instance list, state, size, image, addresses, project, create/delete actions |
| Create instance | Name, Ubuntu image, flavor, private network, SSH public key, optional supported public IP, estimated cost |
| Instance detail | Observed state, timestamps, IPs, attached resources, usage, operation history, assistant diagnostics |
| Networks | Private network/subnet, router/NAT, security groups, supported ingress and IP allocation |
| SSH keys | Public key fingerprints, add/remove, reference usage; no private key input |
| Usage | Resource totals by project and period, daily chart, billable units, rate version, freshness |
| Billing | Prepaid balance, pending top-ups, ledger, statements/receipts, spending limits, add credit |
| Assistant | PeopleWelcome conversation, diagnostic results, proposed change and confirmation card |

The launch estimate is a preview derived from server-owned rates. Show every billable resource, currency, unit, estimate period, and retained-storage/IP behavior. Label public IP support by verified region capability. Whole-dollar top-up options are a design choice; no production price is chosen in this revision.

Always show empty, loading, stale, error, insufficient-credit, quota-exceeded, and permission-denied states. Avoid showing sample VMs or invented billing totals as real account data.

## Roles

| Role | Capabilities |
| --- | --- |
| Owner | Organization settings, membership, billing, limits, and project administration |
| Admin | Projects and infrastructure; no ownership transfer or billing changes by default |
| Member | Authorized project infrastructure and read-only usage; no organization billing administration |
| Viewer | Read-only resources and permitted diagnostics |

Membership scope and explicit project access are checked server-side. An organization role alone must not grant cross-organization access. Separate staff/operator credentials from these roles. Define the final permission matrix in code before inviting customers.

## Main flows

**Registration:** create user, verify email, create organization, then enqueue Keystone project onboarding. Show onboarding status and retryable failures. Do not return a ready-to-launch project until provider setup succeeds.

**Top-up:** choose an allowed amount, create a server-owned top-up intent, open Stripe Checkout, then show pending credit. The dashboard polls for the verified webhook result. The browser return URL cannot create ledger credit.

**Create VM:** select approved catalog entries, show server estimate and quotas, confirm the billable action, and submit an idempotent request. Track the returned operation until OpenStack reports success or failure. Display provider faults without leaking credentials or unrelated tenant data.

**Delete VM:** explain data loss and which volumes/IPs will remain; require confirmation; submit an idempotent delete; retain the row as deleting until confirmed. Offer explicit, separately authorized cleanup of remaining billable resources.

**Assistant change:** display a structured proposal with target project, exact parameters, cost/security impact, expiry, and confirm/cancel. Only the authenticated confirmation action can authorize execution. New model output cannot alter an approved proposal.

## API surface

Use `/api/v1` JSON endpoints. Session authentication applies except registration/login/reset endpoints and signed Stripe webhooks. Mutation endpoints require CSRF protection where cookie-authenticated. IDs below are Nebula IDs, not caller-chosen Keystone project IDs.

| Method and path (under `/api/v1`) | Result / rule |
| --- | --- |
| `POST /auth/register` | Accept registration; generic response avoids email enumeration |
| `POST /auth/verify-email` | Consume a single-use expiring verification token |
| `POST /auth/login`, `POST /auth/logout` | Create/revoke server session; rate limited |
| `POST /auth/password-reset`, `POST /auth/password-reset/complete` | Generic request response; consume expiring token, revoke sessions |
| `GET /me` | Current user and permitted organizations |
| `GET /organizations`, `POST /organizations` | List/create customer organizations |
| `GET /organizations/{org}/members` | Authorized membership list |
| `POST /organizations/{org}/invitations` | Owner invitation with single-use expiring token |
| `POST /invitations/accept` | Verified invitee accepts a membership invitation |
| `PATCH /organizations/{org}/members/{member}` | Owner role/access changes, protected last-owner invariant |
| `DELETE /organizations/{org}/members/{member}` | Owner removes membership, revokes associated access |
| `GET /organizations/{org}/projects`, `POST /organizations/{org}/projects` | List/create project; provisioning is asynchronous |
| `GET /projects/{project}/catalog` | Region-approved flavors, Ubuntu images, rates, capabilities |
| `GET /projects/{project}/instances` | Cursor-paginated project instances with freshness |
| `GET /projects/{project}/instances/{instance}` | Authorized instance detail and resource references |
| `POST /projects/{project}/instance-quotes` | Server cost estimate, rate version, expiry; no resource creation |
| `POST /projects/{project}/instances` | Confirmed billable create, `Idempotency-Key`, `202` operation |
| `DELETE /projects/{project}/instances/{instance}` | Confirmed deletion, idempotent `202` operation |
| `GET /projects/{project}/operations/{operation}` | Operation state and sanitized error |
| `GET /projects/{project}/networks`, `POST /projects/{project}/networks` | Read/create validated private network and subnet |
| `DELETE /projects/{project}/networks/{network}` | Confirmed delete; reject dependencies |
| `GET /projects/{project}/routers`, `POST /projects/{project}/routers` | Read/create router and approved subnet/gateway association |
| `DELETE /projects/{project}/routers/{router}` | Confirmed dependency-aware router deletion |
| `GET /projects/{project}/security-groups`, `POST /projects/{project}/security-groups` | Read/create validated groups and explicit rules |
| `PATCH /projects/{project}/security-groups/{group}` | Confirm exact security rule changes |
| `GET /projects/{project}/public-ips`, `POST /projects/{project}/public-ips` | Capability-gated, quoted IP allocation/association |
| `DELETE /projects/{project}/public-ips/{ip}` | Confirm release and reconcile final metering |
| `GET /projects/{project}/ssh-keys`, `POST /projects/{project}/ssh-keys` | List/register parsed SSH public keys and fingerprints |
| `DELETE /projects/{project}/ssh-keys/{key}` | Remove registered key; explain existing guest keys are unaffected |
| `GET /projects/{project}/usage` | Validated UTC period and resource aggregation |
| `GET /organizations/{org}/billing` | Authorized balance, reservations, freshness, limits |
| `POST /organizations/{org}/billing/checkout-sessions` | Allowed top-up amount, idempotent server-side Checkout creation |
| `GET /organizations/{org}/billing/ledger` | Immutable cursor-paginated entries |
| `GET /organizations/{org}/billing/statements` | Statements and authorized receipt/invoice references |
| `PATCH /organizations/{org}/billing/limits` | Owner sets spending limits; audit change |
| `POST /webhooks/stripe` | Raw-body signature verification and durable event inbox |
| `POST /projects/{project}/assistant/messages` | PeopleWelcome conversation plus authorized tool proposals/results |
| `POST /projects/{project}/confirmations/{confirmation}/execute` | Consume exact, unexpired, actor-bound confirmation |
| `GET /health/live`, `GET /health/ready` | Minimal liveness; readiness checks essential dependencies without secret detail |

## Request and operation contract

An instance request references `name`, `flavor_id`, `image_id`, `network_id`, `ssh_key_id`, an optional public IP request, and an unexpired `quote_id` with its UI confirmation. The server resolves every reference within the current project/catalog and recalculates admission rules. Do not accept arbitrary cloud-init, remote image URLs, or administrative flags in v1.

Use `Idempotency-Key` on retryable mutation requests. Scope it to actor/project/action, persist a canonical request hash, return the original operation on an identical retry, and reject reuse with changed parameters as `409 Conflict`. Upstream retries also require provider reconciliation.

An operation returns `id`, `status`, `action`, `resource_id` when known, `created_at`, `updated_at`, and a sanitized error. States are `queued`, `running`, `reconciling`, `succeeded`, `failed`, and `needs_attention`. A queued delete does not mean a resource has been deleted.

Errors contain `code`, `message`, `request_id`, and field details safe for that caller. Use `401` for no session, `403` for forbidden actions, non-enumerating `404` for inaccessible resources, `409` for conflicts, `422` for invalid fields, `429` for limits, and `503` for unsafe/unavailable provisioning. Require pagination limits and validate time-window bounds.
