"""Render real Terraform host output into the complete pinned Kolla inventory."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import yaml


def render(hosts, template, output, *, management_interface, external_interface, user, private_key, ha_vip=None):
    controls = [n for n, h in hosts.items() if h["role"] == "control"]
    computes = [n for n, h in hosts.items() if h["role"] == "compute"]
    if len(controls) not in (1, 3) or not computes:
        raise ValueError("Cloud deployment requires one or three controllers and at least one compute")
    if len(controls) == 3 and not ha_vip:
        raise ValueError("Three controllers require an independently qualified VIP/LB; no VRRP over L3 is assumed")
    for ident, host in hosts.items():
        if not re.fullmatch(r"[a-zA-Z0-9_]+", ident):
            raise ValueError("Unsafe inventory hostname")
        ipaddress.ip_address(host["address"])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    replacements = {"control": controls, "network": controls, "compute": computes, "monitoring": controls, "storage": [], "deployment": ["localhost ansible_connection=local"]}
    lines, skip = [], False
    for line in Path(template).read_text().splitlines():
        match = re.fullmatch(r"\[([^]]+)\]", line.strip())
        if match:
            group = match[1]
            skip = group in replacements
            lines.append(line)
            if skip:
                lines.extend(replacements[group])
        elif not skip:
            lines.append(line)
    (output / "multinode").write_text("\n".join(lines) + "\n")
    (output / "host_vars").mkdir(exist_ok=True)
    for name, host in hosts.items():
        vars_ = {"ansible_host": host["address"], "ansible_user": user, "ansible_become": True,
            "ansible_ssh_private_key_file": str(Path(private_key).expanduser()),
            "nebula_role": host["role"], "network_interface": management_interface,
            "api_interface": management_interface, "tunnel_interface": management_interface,
            "neutron_external_interface": external_interface,
            "nebula_peer_args": [v for peer in hosts.values() if peer["address"] != host["address"] for v in ["--peer", peer["address"]]]}
        (output / "host_vars" / (name + ".yml")).write_text(yaml.safe_dump(vars_))
    globals_ = {"kolla_internal_vip_address": ha_vip or hosts[controls[0]]["address"],
        "kolla_external_vip_address": ha_vip or hosts[controls[0]]["address"],
        "enable_haproxy": bool(ha_vip), "enable_keepalived": bool(ha_vip)}
    (output / "globals.local.yml").write_text(yaml.safe_dump(globals_))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hosts", required=True, help="terraform output -json hosts (not full state)")
    p.add_argument("--template", required=True, help="Pinned Kolla upstream ansible/inventory/multinode")
    p.add_argument("--output", default=".runtime/kolla")
    p.add_argument("--management-interface", required=True)
    p.add_argument("--external-interface", required=True)
    p.add_argument("--user", default="root")
    p.add_argument("--private-key", required=True)
    p.add_argument("--ha-vip")
    a = p.parse_args()
    render(json.loads(Path(a.hosts).read_text()), a.template, a.output, management_interface=a.management_interface,
        external_interface=a.external_interface, user=a.user, private_key=a.private_key, ha_vip=a.ha_vip)


if __name__ == "__main__":
    main()
