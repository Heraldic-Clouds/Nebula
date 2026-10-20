# Contributing to Nebula

This repository starts with an application design. Use [the roadmap](docs/roadmap.md) to implement connected, testable increments. Do not describe a planned integration as operational.

## Working agreements

- Reuse OpenStack APIs for infrastructure behavior; do not implement a second scheduler, hypervisor manager, or networking control plane.
- Keep the Nebula runtime on ThreeFold. Preserve the original brief's restrictions and approval requirements.
- Require project authorization for every infrastructure lookup and action, including worker and assistant paths.
- Keep wallet mnemonics, SSH private keys, Stripe credentials, application credentials, WireGuard configs, Terraform state, database dumps, and Kolla secrets out of Git.
- Use fixed-point arithmetic, durable idempotency, and database transactions for billing.
- Keep provider-specific code behind adapters. Future integrations must not delay the ThreeFold/OpenStack MVP.
- Use clearly named test fixtures. No simulated capacity, payments, assistant response, or VM status may be presented as a live result.
- Pin dependencies when they are introduced and run the relevant checks before pushing. A passing unit test is not evidence of working infrastructure.

## Evidence and changes

For each implemented milestone, update the status in the README, link the acceptance evidence, and document any remaining limitation. Deployment evidence should identify the commit, tool versions, selected nodes, timestamps, relevant resource IDs, and sanitized test output. Store sensitive raw evidence outside Git.

The author identity requested for this repository is configured locally:

```powershell
git config --local user.name "TantalusDenton"
git config --local user.email "thomasdxdenton@hotmail.com"
```

The repository's existing MIT license applies. Do not remove its copyright notice.
