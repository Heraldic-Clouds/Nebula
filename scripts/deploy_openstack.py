"""Linux operator entry point; never provisions ThreeFold resources."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["prepare", "write-marker", "reboot", "preflight", "deploy"])
    p.add_argument("--inventory", default=".runtime/kolla/multinode")
    p.add_argument("--config-dir", default=".runtime/kolla/config")
    p.add_argument("--external-network-evidence", type=Path,
                   help="Operator-signed-off JSON describing qualified upstream subnet/routing and recovery access")
    p.add_argument("--development-tcg", action="store_true")
    p.add_argument("--transport-mtu", type=int, default=1420)
    a = p.parse_args()
    if sys.platform != "linux":
        p.error("Kolla-Ansible must run on a Linux operator host; no infrastructure action ran")
    inventory = Path(a.inventory).resolve(strict=True)
    config = Path(a.config_dir).resolve()
    if a.stage == "prepare":
        subprocess.run(["ansible-playbook", "-i", str(inventory), str(ROOT / "infra/kolla/prepare.yml")], check=True)
    elif a.stage == "reboot":
        subprocess.run(["ansible", "baremetal", "-i", str(inventory), "-b", "-m", "ansible.builtin.reboot", "-a", "reboot_timeout=600"], check=True)
    elif a.stage in {"write-marker", "preflight"}:
        subprocess.run(["ansible-playbook", "-i", str(inventory), str(ROOT / "infra/kolla/preflight.yml"),
            "-e", json.dumps({"storage_mode": "write" if a.stage == "write-marker" else "verify", "nebula_development_tcg": a.development_tcg})], check=True)
    else:
        # Always rerun capability checks immediately before deployment.
        subprocess.run([sys.executable, __file__, "preflight", "--inventory", str(inventory)] + (["--development-tcg"] if a.development_tcg else []), check=True)
        if not a.external_network_evidence:
            p.error("Supply --external-network-evidence; a host public IP/peer ping does not prove Neutron compatibility")
        evidence = json.loads(a.external_network_evidence.read_text())
        for field in ["approved_by", "approved_at", "provider_subnet", "return_route", "recovery_access", "inventory_sha256"]:
            if not evidence.get(field):
                p.error("External network evidence missing " + field)
        import hashlib
        if evidence["inventory_sha256"] != hashlib.sha256(inventory.read_bytes()).hexdigest():
            p.error("External network evidence does not match this inventory")
        config.mkdir(parents=True, exist_ok=True)
        values = yaml.safe_load((ROOT / "infra/kolla/globals.yml").read_text())
        values.update(yaml.safe_load((inventory.parent / "globals.local.yml").read_text()))
        if not 1280 <= a.transport_mtu <= 9000:
            p.error("Supply the measured transport MTU between 1280 and 9000")
        # Neutron config options are not arbitrary Kolla globals. Emit actual overrides.
        overrides = config / "config"
        overrides.mkdir(parents=True, exist_ok=True)
        (overrides / "neutron.conf").write_text(f"[DEFAULT]\nglobal_physnet_mtu={a.transport_mtu}\n")
        ml2 = overrides / "neutron"
        ml2.mkdir(exist_ok=True)
        (ml2 / "ml2_conf.ini").write_text(f"[ml2]\npath_mtu={a.transport_mtu}\n")
        if a.development_tcg:
            print("DEVELOPMENT ONLY: QEMU/TCG has severe performance limits")
            values["nova_compute_virt_type"] = "qemu"
            override = config / "config/nova"
            override.mkdir(parents=True, exist_ok=True)
            (override / "nova-compute.conf").write_text("[libvirt]\nvirt_type=qemu\ncpu_mode=none\n")
        (config / "globals.yml").write_text(yaml.safe_dump(values))
        passwords = config / "passwords.yml"
        if not passwords.exists():
            import sysconfig
            template = Path(sysconfig.get_path("data")) / "share/kolla-ansible/etc_examples/kolla/passwords.yml"
            passwords.write_text(template.read_text())
            passwords.chmod(0o600)
            subprocess.run(["kolla-genpwd", "-p", str(passwords)], check=True)
        # Host OVS was only used for preflight. Kolla manages its own OVS containers.
        subprocess.run(["ansible", "baremetal", "-i", str(inventory), "-b", "-m", "ansible.builtin.service", "-a", "name=openvswitch-switch state=stopped enabled=false"], check=True)
        subprocess.run(["kolla-ansible", "install-deps"], check=True)
        for command in ["bootstrap-servers", "prechecks", "deploy", "post-deploy"]:
            subprocess.run(["kolla-ansible", command, "-i", str(inventory), "--configdir", str(config)], check=True)
        print("Kolla commands completed. Next: run scripts/openstack_smoke.py; no tenant VM success is assumed.")


if __name__ == "__main__":
    main()
