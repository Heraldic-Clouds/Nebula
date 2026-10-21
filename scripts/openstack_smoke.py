"""Live tenant smoke test. Creates an actual billable Nova guest only with explicit opt-in."""
import argparse
import json
import subprocess
from pathlib import Path
import openstack
from datetime import datetime, timezone


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cloud", required=True, help="Scoped test tenant in private clouds.yaml")
    p.add_argument("--image", required=True)
    p.add_argument("--flavor", required=True)
    p.add_argument("--network", required=True)
    p.add_argument("--key-name", required=True)
    p.add_argument("--ssh-private-key", required=True)
    p.add_argument("--ssh-user", default="ubuntu")
    p.add_argument("--approve-guest-create", action="store_true")
    p.add_argument("--floating-ip", help="Existing approved tenant floating IP to attach; none is purchased automatically")
    p.add_argument("--output", default="reports/openstack-smoke.json")
    a = p.parse_args()
    if not a.approve_guest_create:
        p.error("This creates a real VM. Review quotas/costs and supply --approve-guest-create; no action ran")
    cloud = openstack.connect(cloud=a.cloud)
    report = {"time": datetime.now(timezone.utc).isoformat(), "live": True, "passed": False}
    server = None
    try:
        server = cloud.compute.create_server(name="nebula-acceptance", image_id=a.image, flavor_id=a.flavor,
            networks=[{"uuid": a.network}], key_name=a.key_name)
        report["server_id"] = server.id
        server = cloud.compute.wait_for_server(server, wait=600)
        if a.floating_ip:
            cloud.add_ip_list(server, [a.floating_ip])
            address = a.floating_ip
        else:
            addresses = [item["addr"] for values in server.addresses.values() for item in values if item.get("version") == 4]
            if not addresses:
                raise RuntimeError("Guest has no IPv4 address")
            address = addresses[0]
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15",
            "-i", a.ssh_private_key, f"{a.ssh_user}@{address}", "cloud-init status --wait && uname -a && curl --fail --max-time 15 https://cloud-images.ubuntu.com/"], check=True)
        report["ssh_address"], report["passed"] = address, True
    finally:
        if server:
            cloud.compute.delete_server(server.id, ignore_missing=True)
            cloud.compute.wait_for_delete(server, wait=300)
            report["deleted"] = True
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(json.dumps(report, indent=2))
        cloud.close()


if __name__ == "__main__":
    main()
