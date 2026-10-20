# ThreeFold and OpenStack infrastructure design

Status: unprovisioned. No selected nodes, Terraform resources, Kolla inventory, compatibility result, or approved infrastructure quote exists yet.

## Runtime and blockchain boundary

All Nebula runtime nodes must be on the ThreeFold Grid. Terraform will use `threefoldtech/grid`; Kolla-Ansible will deploy OpenStack 2026.1 services in Docker on Ubuntu 24.04 where supported. WireGuard carries private node management connectivity.

TFChain coordinates grid identities and infrastructure deployment contracts. The operator's wallet authorizes those contracts. OpenStack handles tenant VM scheduling and lifecycle within the provisioned capacity. Customer identities, workload contents, payment data, chat transcripts, and Nebula usage journals stay off-chain.

The brief authorizes design work; it explicitly does not authorize buying capacity. Do not run a billable Terraform apply without approval of selected nodes and the proposed spend.

## Staged topology

| Stage | ThreeFold nodes | Purpose |
| --- | --- | --- |
| Compatibility probe | One test VM, then a peer VM when approved | Verify virtualization and inter-node networking before an OpenStack deployment |
| Development pilot | One controller/network node and one compute node | Minimum role-separated OpenStack deployment; no HA claim |
| Public MVP target | Controller/network, compute, and separate application/database capacity | Isolate customer services from the cloud control plane |
| Controller expansion | Three controllers plus compute and application capacity | Only after quorum, latency, ingress, failover, and storage qualifications |

Initial sizing hypotheses for planning: controller 4 vCPU / 16 GB RAM / 100 GB persistent SSD; compute 8 vCPU / 32 GB RAM / 200 GB persistent SSD; separate application node 2-4 vCPU / 8 GB RAM / 80 GB persistent SSD. These are neither provider requirements nor selected-node availability claims. Benchmark actual capacity, reserve overhead, and quote actual nodes before approval.

Controller services: Keystone, Glance, Nova API/Scheduler/Conductor, Placement, Neutron API/agents, Horizon, MariaDB, RabbitMQ, required caches and Kolla support services. Compute services: Nova Compute, libvirt/KVM, Neutron's required compute agents. Network roles: tenant DHCP, metadata, routing/NAT, security groups, and verified external ingress.

## Critical compatibility gate

Record node ID, farm, region, VM type/image digest, kernel, sizing, tool versions, time, and sanitized evidence for each test. Until the tests actually run, every result is **unverified**.

| Check | Required evidence and stop condition |
| --- | --- |
| Root and SSH | Authenticated key login and required sudo/root operations; stop if required access is unavailable |
| Host image/kernel | Supported Ubuntu 24.04 boot, Docker operation, required modules/capabilities; stop affected services if incompatible |
| CPU flags | Capture `lscpu` and virtualization flags; flags alone do not prove nested guests work |
| `/dev/kvm` | Device exists, correct permissions, usable by libvirt/QEMU service context |
| Nested virtualization | Boot a real nested guest with explicit KVM acceleration and record successful execution; stop production compute if unavailable |
| QEMU/TCG fallback | If needed, deliberately test Nova with `qemu` and TCG in an isolated development configuration; label severe performance limits and measure them |
| Resources | Record available CPU, memory, actual disk capacity, pressure and service overhead |
| Persistent storage | Write evidence, reboot the VM, verify data and mounts survive; document node-failure/redeployment limits separately |
| Peer network | Bidirectional VM-to-VM traffic across approved nodes over WireGuard; record route, firewall, loss, latency, and MTU |
| Network privileges | Test namespace, veth, bridge/OVS, forwarding and filtering operations needed by Neutron in the actual VM type |
| Tenant overlay | Test the selected VXLAN or other supported Neutron overlay across nodes; verify encapsulation and guest MTU end-to-end |
| External networking | Prove upstream routing/allocation supports the intended Neutron external subnet and return traffic; a public address on a host is insufficient |
| Tenant reachability | Real guest obtains network configuration, accesses outbound network, and receives permitted inbound traffic; security group denial also works |
| Operator endpoint | Verify the management/API/Horizon endpoint and DNS/TLS path without exposing internal control-plane ports |

ThreeFold documents different kernel control for micro and full VMs. Prefer evaluating a full VM for the OpenStack host; this is a candidate design choice, not proof of nested KVM or networking support. Verify image support and Terraform full-VM semantics against the selected provider version. See [primary references](sources.md).

### Non-mutating host inventory examples

After an approved test VM exists, capture initial facts over SSH:

```bash
uname -a
id
lscpu
ls -l /dev/kvm
free -h
lsblk -f
df -hT
ip -br address
ip route
ip -d link show
```

These commands inventory a host; they do not pass the compatibility gate. Nested guest boot, OVS/namespace exercises, disk reboot verification, and connectivity tests change host state and need explicit procedures in the implemented preflight tooling. A production result requires a Nova-launched tenant guest, not only a stand-alone QEMU process.

## Networking choices

Keep management connectivity, tenant overlay traffic, and the external/provider path conceptually separate. WireGuard supplies an L3 private network; it does not itself provide a Neutron external L2 segment, public address pool, or floating-IP return route. Determine whether the selected ThreeFold setup supports a routed public subnet, an appropriate bridgeable provider network, or another verified ingress path.

The proposed pilot uses ML2/Open vSwitch with private tenant networks and a centralized Neutron router. Its actual bridge mappings, interfaces, overlay addresses, and MTU remain configuration outputs of preflight. Do not bridge the sole SSH management interface into `br-ex` by assumption. Preserve an out-of-band recovery path before network changes.

If only limited NAT/port ingress works, record the limitation and do not advertise general floating IPs. Unsupported public networking blocks that feature and any release acceptance that depends on it. Unsupported tenant networking blocks OpenStack deployment.

## Storage policy

Avoid Ceph in v1. Start by qualifying persistent ThreeFold-backed disks for controller state, Glance image storage, Nova instance storage, and the Nebula database. A persistent disk is not a replicated volume service, backup, or node-failure recovery guarantee.

Do not turn on Cinder without selecting and testing a supported backend. If the first pilot only supports persistent root disks tied to a compute node, document that limitation, meter the provisioned root capacity, and do not advertise detachable volumes, live migration, or automatic instance recovery. Back up control-plane/application state to approved ThreeFold-hosted capacity and test restores. Storj remains deferred.

## Terraform and Kolla implementation contract

Implement `infra/terraform` in two isolated stages: a small preflight deployment and the cloud node deployment. Pin the provider and commit its dependency lock file. Select exact node IDs and verified image references; avoid a mutable `latest` image for repeatable deployments.

The cloud topology should accept a named controller map with one or three entries and a separate compute map, using stable `for_each` keys. Emit sanitized private addresses and inventory inputs. Treat WireGuard configuration, wallet mnemonics, plans and state as sensitive. Keep state in encrypted, access-controlled operator storage or a verified ThreeFold-hosted backend with locking; never put it in Git or public CI artifacts.

Generate Kolla inventory from actual node outputs, retaining complete upstream inventory groups for the pinned Kolla release. Parameterize management/tunnel/external interfaces and endpoints from evidence. Default to KVM. A QEMU experiment requires explicit development mode and a visibly different inventory/configuration. Run Kolla prechecks before deployment, and retain sanitized reports.

Three controllers require proven MariaDB/RabbitMQ quorum, stable low-latency networking, load-balanced API endpoints and failover, plus tested recovery. Do not assume a Keepalived VIP/VRRP can move across an L3 WireGuard network. Expanding controller count does not make single-node Glance data, application PostgreSQL, or compute disks highly available.

## Cost worksheet

**Current estimate: unavailable because actual nodes have not been selected. Current resources purchased by this task: none.**

Capture the following before requesting approval for a deployment:

| Field | Required value |
| --- | --- |
| Selection time and network | Timestamp and exact ThreeFold environment |
| Each host | Node/farm ID, location, measured capabilities, VM type, CPU, RAM, disk |
| Quote | Provider quote/calculator output and applicable conditions for those nodes |
| Public IP | Quantity, availability and quoted cost |
| Storage/backup | Capacity, retention and quoted cost |
| Currency | TFT and displayed currency conversion source/time when applicable |
| Duration | Maximum preflight/pilot duration and expected total cost over that duration |
| Operator reserve | Wallet funding buffer and monitoring threshold |
| Approval | Approved nodes, budget, duration, cleanup and preserved-data policy |

Do not substitute a generic ThreeFold marketing price for an actual selected-node estimate. Customer selling rates and operator infrastructure costs are separate decisions.
