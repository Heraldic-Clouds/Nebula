#!/usr/bin/env python3
"""Run on each Linux OpenStack host as root. Writes JSON and exits nonzero on any blocker."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone


def run(args, timeout=20):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def guest_probe(accel):
    """Boot actual x86 guest instructions and emit a serial marker; no mock KVM result."""
    marker = b"NEBULA_NESTED_CPU_OK"
    # 16-bit BIOS boot sector: serial output, then isa-debug-exit. QEMU must execute it.
    code = b"\xfa\x31\xc0\x8e\xd8\xba\xf8\x03"
    code += b"".join(b"\xb0" + bytes([c]) + b"\xee" for c in marker)
    code += b"\xba\xf4\x00\xb0\x00\xee\xf4\xeb\xfd"
    boot = code.ljust(510, b"\0") + b"\x55\xaa"
    with tempfile.TemporaryDirectory(prefix="nebula-guest-") as temp:
        image = Path(temp) / "probe.img"
        image.write_bytes(boot)
        result = run(["qemu-system-x86_64", "-accel", accel, "-m", "128", "-smp", "1",
            "-drive", f"file={image},format=raw,if=floppy", "-boot", "a", "-display", "none",
            "-serial", "stdio", "-monitor", "none", "-no-reboot",
            "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04"], timeout=30)
        if marker.decode() not in result.stdout:
            raise RuntimeError(f"Guest did not execute under {accel}; QEMU exit={result.returncode}: {result.stderr[-500:]}")
        return {"accelerator": accel, "guest_executed": True, "probe": "BIOS CPU smoke test; Nova Ubuntu boot still required"}


def privilege_probe():
    suffix = uuid.uuid4().hex[:8]
    ns, left, right, bridge = "nb" + suffix, "nl" + suffix, "nr" + suffix, "nb" + suffix
    try:
        for command in [["ip", "netns", "add", ns], ["ip", "link", "add", left, "type", "veth", "peer", "name", right],
                        ["ip", "link", "set", right, "netns", ns], ["modprobe", "openvswitch"],
                        ["ovs-vsctl", "--timeout=10", "add-br", bridge],
                        ["ovs-vsctl", "--timeout=10", "add-port", bridge, left],
                        ["ip", "netns", "exec", ns, "iptables", "-t", "nat", "-L"]]:
            result = run(command)
            if result.returncode:
                raise RuntimeError(f"{command[0:3]} failed: {result.stderr[-300:]}")
        return {"netns": True, "veth": True, "ovs_bridge": True, "iptables_nat": True}
    finally:
        run(["ovs-vsctl", "--timeout=5", "--if-exists", "del-br", bridge])
        run(["ip", "link", "del", left])
        run(["ip", "netns", "del", ns])


def storage_probe(directory, mode):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / ".nebula-persistence-probe.json"
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if mode == "write":
        payload = uuid.uuid4().hex
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump({"boot_id": boot_id, "payload": payload, "sha256": hashlib.sha256(payload.encode()).hexdigest()}, file)
            file.flush()
            os.fsync(file.fileno())
        raise RuntimeError(f"PERSISTENCE_PENDING: marker written to {marker}. Reboot, then rerun with --storage-mode verify")
    data = json.loads(marker.read_text())
    if data["boot_id"] == boot_id:
        raise RuntimeError("PERSISTENCE_PENDING: host has not rebooted since marker was written")
    if hashlib.sha256(data["payload"].encode()).hexdigest() != data["sha256"]:
        raise RuntimeError("Persistence marker checksum mismatch")
    disk = shutil.disk_usage(directory)
    return {"path": str(directory), "survived_reboot": True, "free_bytes": disk.free,
            "mount": run(["findmnt", "-J", "-T", str(directory)]).stdout.strip()}


def check_interface(name, external=False):
    result = run(["ip", "-j", "address", "show", "dev", name])
    if result.returncode:
        raise RuntimeError(f"Interface {name} not found")
    info = json.loads(result.stdout)[0]
    if "UP" not in info["flags"]:
        raise RuntimeError(f"Interface {name} must be UP")
    if external and any(a.get("scope") == "global" for a in info["addr_info"]):
        raise RuntimeError("External interface carries a host IP; do not bridge away management access")
    return info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["control", "compute"], required=True)
    parser.add_argument("--management-interface", required=True)
    parser.add_argument("--external-interface")
    parser.add_argument("--peer", action="append", default=[])
    parser.add_argument("--management-mtu", type=int, default=1420)
    parser.add_argument("--storage-path", default="/var/lib/docker")
    parser.add_argument("--storage-mode", choices=["write", "verify"], required=True)
    parser.add_argument("--development-tcg", action="store_true")
    parser.add_argument("--output", default="/var/tmp/nebula-preflight.json")
    args = parser.parse_args(argv)
    report = {"host": socket.gethostname(), "role": args.role, "kernel": platform.release(),
        "time": datetime.now(timezone.utc).isoformat(), "development_only": args.development_tcg,
        "nova_guest_verified": False, "neutron_external_verified": False, "checks": {}}

    def check(name, action):
        try:
            report["checks"][name] = {"passed": True, "detail": action()}
        except Exception as exc:
            report["checks"][name] = {"passed": False, "detail": str(exc)}

    def root():
        if platform.system() != "Linux" or os.geteuid() != 0:
            raise RuntimeError("Run on the intended Linux ThreeFold host with root/sudo")
        return {"root": True}
    check("root", root)
    if report["checks"]["root"]["passed"]:
        check("management_interface", lambda: check_interface(args.management_interface))
        check("network_privileges", privilege_probe)
        check("persistent_storage", lambda: storage_probe(args.storage_path, args.storage_mode))
        check("inventory", lambda: {"cpu": run(["lscpu", "-J"]).stdout, "memory": run(["free", "-b"]).stdout, "disks": run(["lsblk", "-J", "-f"]).stdout})
        for peer in args.peer:
            def peer_check(peer=peer):
                # IPv4 DF checks validate the usable private path MTU, not Neutron/provider routing.
                result = run(["ping", "-4", "-c", "3", "-W", "3", "-M", "do", "-s", str(args.management_mtu - 28), peer])
                if result.returncode:
                    raise RuntimeError(f"Peer/MTU check failed for {peer}: {result.stdout[-300:]}")
                return {"peer": peer, "mtu": args.management_mtu}
            check("peer_" + peer, peer_check)
        if not args.peer:
            report["checks"]["peer_network"] = {"passed": False, "detail": "Supply a peer host; VM-to-VM networking is unverified"}
        if args.role == "control":
            if args.external_interface:
                check("external_interface", lambda: check_interface(args.external_interface, external=True))
            else:
                report["checks"]["external_interface"] = {"passed": False, "detail": "Supply the qualified provider interface; no interface is guessed"}
        if args.role == "compute":
            check("nested_cpu", lambda: guest_probe("tcg" if args.development_tcg else "kvm"))
            check("cpu_flags", lambda: Path("/proc/cpuinfo").read_text()[:6000])
    report["passed"] = all(c["passed"] for c in report["checks"].values())
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
