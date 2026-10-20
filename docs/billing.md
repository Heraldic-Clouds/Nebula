# Prepaid billing and metering

Status: design only. Stripe integration, collection workers, ledger migrations, and rate configuration are not implemented.

## Separation of responsibilities

Stripe collects customer top-ups through hosted Checkout. Nebula records prepaid credit and charges its own ledger for observed resource usage. ThreeFold infrastructure contracts are paid separately by the operator's wallet; customer top-ups never grant access to that wallet. Keep development and CI in separate Stripe sandboxes/test environments. Live payments remain disabled until end-to-end reconciliation passes.

The customer wallet is a service-credit accounting balance, not an on-chain asset. Marco Polo coin payments are deferred. Rates are versioned server-side configuration, with a currency, effective timestamp, and explicit unit. No sales price has been selected in this design.

## Payment flow

1. An authorized owner selects an allowed whole-dollar top-up amount. The backend validates currency, amount, organization, Stripe customer mapping, and limits.
2. Persist a top-up intent and create a Checkout Session with a stable idempotency key. Store the returned session ID. Include an opaque intent reference; do not trust arbitrary client metadata as a tenant association.
3. Redirect to Stripe-hosted Checkout. Omit a hard-coded payment-method list so the configured eligible methods can be used.
4. At the webhook endpoint, verify the signature against the **raw HTTP request body** with the endpoint's signing secret, using the official SDK and timestamp tolerance. Reject invalid signatures before any mutation.
5. Persist the verified event in an inbox with a unique Stripe event ID, then acknowledge after durable acceptance. Repeated delivery is a no-op or resumes processing.
6. For `checkout.session.completed` and `checkout.session.async_payment_succeeded`, retrieve/verify the current session when needed. Require `payment_status=paid`, the expected customer, intent/session association, currency, amount, and expected non-live environment before crediting.
7. Within one transaction, claim fulfillment by the **Checkout session ID**, post the balanced top-up journal, and mark the intent fulfilled. Both event IDs and fulfillment identity are required: two event types can refer to the same payment.
8. The dashboard reads the ledger result. A return URL, frontend response, or incomplete payment grants no balance. Failed/expired asynchronous payments remain uncredited.

Use restricted server-side API keys with the required permissions, separate webhook secrets per endpoint/environment, an explicitly pinned API version, and a per-instance Stripe client. Pin the SDK and verify its current parameter contract during implementation. Log Stripe object IDs and redacted errors, never credentials or payment details.

## Ledger invariants

- Use immutable balanced journals and postings, not ad hoc increments of a balance field. Each journal balances within a single currency.
- Represent internal money as integer micro-units of the currency; Stripe amounts use that currency's supported minor unit. Use decimal/fixed-point arithmetic and explicit conversions, never binary floating point.
- A top-up increases customer credit liability against payment clearing. Usage reduces that liability against earned usage revenue. Do not bill a second charge to a card for usage already deducted from credit.
- Protect the balance projection and reservations with PostgreSQL row locks or equivalent serializable admission transactions. Concurrent creates must not spend the same available credit or quota.
- Give every top-up, usage settlement, refund, dispute, and manual adjustment a durable unique source reference. Refund/dispute processing must also track the underlying object and cumulative amount across multiple event IDs.
- Corrections use new reversal/adjustment journals. Do not edit or delete settled ledger entries. Keep the original rate version and usage evidence.
- Reconcile verified payments to credited journals and reconcile the balance projection to postings. Alert on divergence; hold new provisioning when reconciliation is unsafe.

Refunds and disputes create compensating entries for the actual change in settled amount. Repeated or out-of-order events must not double-debit. Recompute available credit and flag any resulting shortfall. Operators review these cases; no automatic tenant deletion is part of v1.

## Billable units and lifecycle

| Resource | Unit | Proposed charging policy |
| --- | --- | --- |
| vCPU allocation | vCPU-hour | Allocated vCPUs while a successfully created instance exists, including stopped instances; exclude failed builds with no usable allocation |
| RAM allocation | GB-hour | Allocated RAM while the instance exists under the same policy as vCPU; show this policy before launch |
| Persistent storage | GB-month | Provisioned supported root/volume capacity while retained, including after VM deletion when explicitly retained |
| Public IP | IP-hour | Assigned/reserved address while allocated, including unattached addresses, only where supported |

These are proposed Nebula customer policies and must be explicitly accepted before launch. Track actual provider states rather than inferring allocation from CPU utilization. Decide and test handling of shelved/offloaded states before exposing those operations; v1 exposes creation/deletion only.

Define customer-facing `GB` as decimal gigabytes. Convert OpenStack MB/GiB-reported quantities explicitly and preserve original units. For a simple, stable billing convention, define one storage GB-month as **730 GB-hours** and disclose it. Use UTC half-open intervals `[start, end)`.

For interval duration `s` seconds, allocated `c` vCPUs, `m` GB RAM, `d` GB storage, and `p` IPs:

```text
usage_cost =
    (c * s / 3600) * cpu_rate_per_vcpu_hour
  + (m * s / 3600) * ram_rate_per_gb_hour
  + (d * s / (730 * 3600)) * storage_rate_per_gb_month
  + (p * s / 3600) * public_ip_rate_per_ip_hour
```

Collect observations on a proposed five-minute cadence and settle hourly. Split intervals at resource size/state changes and rate boundaries. Carry fractional micro-unit remainders forward per billing stream so rounding each collection interval cannot inflate charges. Settle the final interval when deletion/release is confirmed. Display minor-unit statement totals using a documented rounding policy and reconcile them to carried balances.

## Sources and collection

Use Nova server details and instance-action/event history where available, Neutron ports/floating IPs, Glance image metadata, and supported volume inventories. A future Cinder adapter is only enabled after its backend passes storage qualification. Do not infer durable storage from an image's download size.

Persist raw normalized observations before rating. Snapshot polling alone can miss a VM created and deleted between polls. Record Nebula operations, consume available OpenStack lifecycle notifications/history, and reconcile Horizon-created or altered resources. Keep a coverage watermark per project; missing coverage or an unresolved resource lifecycle creates a billing gap for review, not invented usage. Gate launch readiness on a proven strategy for short-lived instances and out-of-band changes.

Collector failure must not turn stale data into zero usage. Mark usage stale, retry with backoff, alert, and reject new provisioning when the configured freshness threshold is exceeded. State changes discovered late are corrected with auditable journals and preserved evidence.

## Admission and spending limits

Available credit is settled credit minus settled usage minus active reservations and a configurable allowance for observed but unsettled usage. Before provisioning, validate the requested cost estimate, quota, current balance, estimated pending spend, and organization spending cap in one admission transaction.

Reserve a documented coverage horizon for the new resource. Expiring a hold requires checking whether its remote resource actually exists. When credit is insufficient, reject **new billable provisioning** and clearly explain the deficit. Continue metering existing resources and notify the customer. This policy can accrue operator exposure while resources remain active; choose explicit notification/escalation terms before public launch. Stopping an instance may still retain billable allocations and storage, so it is not an automatic cure.

Spending limits gate admission using committed usage and reservations and trigger alerts. Do not promise an absolute real-time spending cap while interval metering and continued running resources can exceed it. Any future automatic stop/deletion policy requires separate customer terms and recovery design.

## Statements and reconciliation

Store Stripe receipt and, when configured, invoice references for each paid top-up. Generate Nebula usage statements from immutable ledger lines with units, period, rates, adjustments, and closing balance. A prepaid receipt and a usage statement describe different events; do not present the same usage as a second unpaid Stripe invoice.

Before enabling live payments, validate duplicate/concurrent/out-of-order webhooks, delayed success, wrong currency/customer/amount, invalid signatures, refund/dispute adjustments, ambiguous Checkout creation, metering gaps, deletion boundaries, rounding, concurrent admission, and full settlement-to-payment reconciliation. Public tax/invoice requirements remain a launch decision; do not claim tax collection is configured.

Reference: [Stripe Checkout fulfillment](https://docs.stripe.com/checkout/fulfillment), [webhook signatures](https://docs.stripe.com/webhooks/signature), and [restricted API keys](https://docs.stripe.com/keys/restricted-api-keys).
