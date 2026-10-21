"""Real project-scoped OpenStack SDK adapter. No development provider fallback."""
from datetime import datetime, timezone
from fastapi import HTTPException
from openstack.connection import Connection
from .security import decrypt_credentials


def date(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


class Cloud:
    def __init__(self, project):
        self.project = project
        cred = decrypt_credentials(project.credential)
        self.conn = Connection(
            auth_type="v3applicationcredential",
            auth={"auth_url": project.auth_url, "application_credential_id": cred["id"], "application_credential_secret": cred["secret"]},
            region_name=project.region, interface=project.interface,
            verify=project.ca_file or True, api_timeout=25, connect_retries=0,
            compute_api_version="2.79", load_yaml_config=False, load_envvars=False,
        )
        if self.conn.session.get_project_id() != project.provider_id:
            raise HTTPException(503, "OpenStack credential project does not match the customer's assigned project")

    def close(self):
        self.conn.close()

    def catalog(self):
        allowed = self.project.catalog
        flavors = []
        for ident in allowed.get("flavors", []):
            f = self.conn.compute.get_flavor(ident)
            # Zero-sized root disks and extra ephemeral/swap disks cannot be rated by this pilot.
            if f.disk > 0 and not f.ephemeral and not f.swap:
                flavors.append({"id": f.id, "name": f.name, "vcpus": f.vcpus, "ram_mb": f.ram, "disk_gb": f.disk})
        images = []
        for ident in allowed.get("images", []):
            image = self.conn.image.get_image(ident)
            if image.status == "active":
                images.append({"id": image.id, "name": image.name})
        networks = []
        for ident in allowed.get("networks", []):
            n = self.conn.network.get_network(ident)
            if n.project_id != self.project.provider_id:
                raise HTTPException(503, "Assigned tenant network has incorrect project ownership")
            networks.append({"id": n.id, "name": n.name})
        keys = [{"name": k.name, "fingerprint": k.fingerprint} for k in self.conn.compute.keypairs()]
        return {"flavors": flavors, "images": images, "networks": networks, "keys": keys}

    def validate(self, request):
        catalog = self.catalog()
        for plural, field in [("flavors", "flavor_id"), ("images", "image_id"), ("networks", "network_id")]:
            if request[field] not in [item["id"] for item in catalog[plural]]:
                raise HTTPException(422, f"Select an operator-approved {field}")
        if request["key_name"] not in [k["name"] for k in catalog["keys"]]:
            raise HTTPException(422, "SSH key is not available to this customer")
        return next(f for f in catalog["flavors"] if f["id"] == request["flavor_id"])

    def keys_add(self, name, public_key):
        if not public_key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")) or "PRIVATE" in public_key:
            raise HTTPException(422, "Only an SSH public key is accepted")
        from cryptography.hazmat.primitives.serialization import load_ssh_public_key
        try:
            load_ssh_public_key(public_key.encode())
        except ValueError as exc:
            raise HTTPException(422, "Invalid SSH public key") from exc
        result = self.conn.compute.create_keypair(name=name, public_key=public_key)
        return {"name": result.name, "fingerprint": result.fingerprint}

    def owned(self, server):
        if server and server.project_id != self.project.provider_id:
            raise HTTPException(404, "Instance not found")
        return server

    def get(self, ident):
        from openstack.exceptions import ResourceNotFound
        try:
            return self.owned(self.conn.compute.get_server(ident))
        except ResourceNotFound:
            return None

    def find_operation(self, operation_id):
        return [self.owned(s) for s in self.conn.compute.servers(details=True)
                if (s.metadata or {}).get("nebula_operation") == operation_id]

    def create(self, operation_id, request):
        self.validate(request)
        return self.owned(self.conn.compute.create_server(
            name=request["name"], image_id=request["image_id"], flavor_id=request["flavor_id"],
            networks=[{"uuid": request["network_id"]}], key_name=request["key_name"],
            metadata={"nebula_operation": operation_id, "nebula_managed": "true"},
        ))

    def delete(self, ident):
        if self.get(ident):
            self.conn.compute.delete_server(ident, ignore_missing=True)
