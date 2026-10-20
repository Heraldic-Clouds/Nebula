# Primary references and verification limits

Research date: 19 October 2026. The supplied [project brief](brief.md) controls scope. References below support specific design choices; they are not evidence of an actual Nebula deployment.

| Reference | What it establishes / limit |
| --- | --- |
| [Kolla-Ansible 2026.1 support matrix](https://docs.openstack.org/kolla-ansible/2026.1/user/support-matrix) | Lists Ubuntu 24.04 as a supported host OS. Does not establish nested virtualization support on ThreeFold. |
| [Kolla-Ansible 2026.1 deployment quick start](https://docs.openstack.org/kolla-ansible/2026.1/user/quickstart.html) | Upstream tool installation, inventory/configuration and deployment command sequence. Its standard networking assumptions require validation on the selected grid VMs. |
| [Kolla-Ansible Neutron networking](https://docs.openstack.org/kolla-ansible/2026.1/reference/networking/neutron.html) | External interfaces/bridges and ML2/OVS configuration. WireGuard reachability alone is insufficient evidence for the provider network. |
| [ThreeFold Terraform provider source](https://github.com/threefoldtech/terraform-provider-grid) | Provider implementation/examples and the place to verify version-specific resource schemas before writing Terraform. No provider configuration has been validated here. |
| [ThreeFold Terraform provider registry](https://registry.terraform.io/providers/threefoldtech/grid/latest/docs) | Provider documentation entry point. Pin an exact version and verify its schema at implementation; do not rely on a moving `latest` contract. |
| [ThreeFold micro/full VM differences](https://manual.grid.tf/labs/documentation/dashboard/deploy/vm_intro/vm_differences/) | Documents differing OS/kernel/image behavior. It does not guarantee `/dev/kvm`, nested KVM, or arbitrary Neutron operations. |
| [ThreeFold TFChain](https://manual.grid.tf/labs/documentation/dashboard/tfchain/) | Describes grid identity and workload contract coordination, supporting the separation between blockchain allocation and OpenStack guest execution. |
| [Stripe Checkout fulfillment](https://docs.stripe.com/checkout/fulfillment) | Server fulfillment, paid session verification, duplicate invocation handling, delayed success, and required webhooks. |
| [Stripe webhook signature verification](https://docs.stripe.com/webhooks/signature) | Signature validation against the original request payload with the endpoint signing secret. |
| [Stripe restricted API keys](https://docs.stripe.com/keys/restricted-api-keys) | Least-privilege server-side API access. |

## Open questions

- Which actual ThreeFold node/image combinations permit nested KVM and necessary kernel/network operations?
- What public address allocation and return routing model can Neutron use on those nodes?
- What storage behavior survives VM reboot, node loss, and workload redeployment respectively?
- Can the required Kolla API endpoint/VIP model work over the selected L3 management topology, including a future three-controller setup?
- What are the real quote, availability, and wallet funding requirements for the selected nodes?
- What is the documented PeopleWelcome endpoint/protocol, and what are its authentication and data-retention terms?
- What email verification/password reset delivery route and public operational policies will Nebula use?

Do not interpret an unanswered question as supported behavior. Record capability findings from actual nodes and actual API calls during the corresponding milestone.
