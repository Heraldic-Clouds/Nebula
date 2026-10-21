# Nebula dashboard boundary

Implemented React/TypeScript console: customer login, VM create/list/delete, public SSH keys, settled usage, prepaid test billing and PeopleWelcome chat. All requests go to the real same-origin `/api/v1` backend.

Run `pnpm install --frozen-lockfile` then `pnpm build` in this directory. The backend serves `dist`; `pnpm dev` proxies API traffic to port 8080 (set the backend's public URL to the dev origin for CSRF checks). Browser code receives no Keystone, Stripe, wallet or PeopleWelcome secrets.

Network setup and project binding are operator tasks in this pilot. Horizon remains the administration dashboard. Missing provider configuration is shown as an error, never replaced with simulated VMs or credit.
