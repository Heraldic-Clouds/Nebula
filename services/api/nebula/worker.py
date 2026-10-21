"""Durable VM operations and observed OpenStack usage. Run as a separate process."""
import argparse
import logging
import time
from datetime import timedelta
from sqlalchemy import select, or_
from .billing import release, settle
from .cloud import Cloud, date
from .config import settings
from .db import transaction
from .models import Audit, Instance, Operation, Project, User, now

log = logging.getLogger("nebula.worker")


def claim():
    with transaction() as db:
        op = db.scalar(select(Operation).where(
            Operation.status.in_(["queued", "running", "reconciling"]), Operation.available_at <= now(),
            or_(Operation.lease_until.is_(None), Operation.lease_until < now()),
        ).order_by(Operation.created_at).with_for_update(skip_locked=True).limit(1))
        if not op:
            return None
        op.lease_until = now() + timedelta(minutes=3)
        op.attempts += 1
        project = db.get(Project, op.project_id)
        instance = db.get(Instance, op.instance_id)
        return op, project, instance


def run_operation():
    claimed = claim()
    if not claimed:
        return False
    op, project, instance = claimed
    cloud = None
    try:
        cloud = Cloud(project)
        if op.action == "create":
            found = cloud.find_operation(op.id)
            if len(found) > 1:
                raise RuntimeError("multiple_remote_resources")
            if found:
                remote = found[0]
            elif instance.provider_id:
                remote = cloud.get(instance.provider_id)
                if remote is None:
                    raise RuntimeError("created_resource_missing")
            elif op.status == "queued":
                if not settings().provisioning_enabled:
                    with transaction() as db:
                        paused = db.get(Operation, op.id)
                        paused.lease_until = None
                        paused.available_at = now() + timedelta(seconds=60)
                        paused.error = "provisioning_disabled"
                    return True
                # Commit dispatch before the network call. A crash must reconcile, never blindly recreate.
                with transaction() as db:
                    current = db.get(Operation, op.id)
                    current.status = "reconciling"
                remote = cloud.create(op.id, instance.request)
            else:
                raise RuntimeError("ambiguous_create_requires_operator_reconciliation")
            with transaction() as db:
                user = db.scalar(select(User).where(User.id == project.user_id).with_for_update())
                current = db.get(Operation, op.id)
                local = db.scalar(select(Instance).where(Instance.id == instance.id).with_for_update())
                local.provider_id, local.state = remote.id, remote.status
                local.addresses, local.observed_at = remote.addresses or {}, now()
                if remote.status == "ACTIVE":
                    local.last_metered_at = local.last_metered_at or date(remote.launched_at) or now()
                    release(user, local)
                    current.status = "succeeded"
                elif remote.status == "ERROR":
                    # Retain reservation until the failed remote allocation has been deleted/reconciled.
                    current.status, current.error = "needs_attention", "nova_build_error"
                else:
                    current.status = "reconciling"
                current.lease_until = None
                current.available_at = now() + timedelta(seconds=15)
                db.add(Audit(user_id=user.id, action="create_observed", detail={"operation": op.id, "status": remote.status}))
        else:
            remote = cloud.get(instance.provider_id)
            if remote:
                with transaction() as db:
                    current = db.get(Operation, op.id)
                    current.status = "reconciling"
                    local = db.get(Instance, instance.id)
                    local.observed_at = now()
                cloud.delete(instance.provider_id)
            with transaction() as db:
                user = db.scalar(select(User).where(User.id == project.user_id).with_for_update())
                local = db.scalar(select(Instance).where(Instance.id == instance.id).with_for_update())
                current = db.get(Operation, op.id)
                if remote is None:
                    # Conservatively settle only to last confirmed presence, not the later 404 time.
                    settle(db, user, local, local.observed_at or now(), final=True)
                    local.deleted_at, local.state = now(), "DELETED"
                    release(user, local)
                    current.status = "succeeded"
                    db.add(Audit(user_id=user.id, action="delete_observed", detail={"operation": op.id, "provider_id": local.provider_id}))
                current.lease_until = None
                current.available_at = now() + timedelta(seconds=15)
    except Exception as exc:
        log.warning("operation %s failed: %s", op.id, type(exc).__name__)
        with transaction() as db:
            current = db.get(Operation, op.id)
            current.status = "needs_attention"
            current.error = "provider_reconciliation_required"
            current.lease_until = None
            db.add(Audit(user_id=project.user_id, action="operation_error", detail={"operation": op.id, "error_type": type(exc).__name__}))
    finally:
        if cloud:
            cloud.close()
    return True


def collect_project(project_id):
    with transaction() as db:
        project = db.get(Project, project_id)
    cloud = None
    try:
        cloud = Cloud(project)
        remotes = {s.id: cloud.owned(s) for s in cloud.conn.compute.servers(details=True)}
        observed = now()
        with transaction() as db:
            user = db.scalar(select(User).where(User.id == project.user_id).with_for_update())
            project = db.get(Project, project_id)
            locals_ = list(db.scalars(select(Instance).where(Instance.project_id == project_id, Instance.deleted_at.is_(None)).with_for_update()))
            managed_ids = {i.provider_id for i in locals_ if i.provider_id}
            # A dispatched create may not have saved its provider ID yet; exclude its operation tag.
            known_ops = set(db.scalars(select(Operation.id).where(Operation.project_id == project_id, Operation.action == "create")))
            unmanaged = [s for s in remotes.values() if s.id not in managed_ids and (s.metadata or {}).get("nebula_operation") not in known_ops]
            error = "unmanaged_instances_present" if unmanaged else None
            for local in locals_:
                if not local.provider_id:
                    continue
                remote = remotes.get(local.provider_id)
                if remote is None:
                    # Never invent a deletion timestamp or a missing interval.
                    settle(db, user, local, local.observed_at or observed, final=True)
                    local.state, local.deleted_at = "DELETED", observed
                    release(user, local)
                    continue
                flavor = remote.flavor or {}
                if "vcpus" in flavor and (int(flavor["vcpus"]) != local.vcpus or int(flavor.get("ram", local.ram_mb)) != local.ram_mb or int(flavor.get("disk", local.disk_gb)) != local.disk_gb):
                    error = "out_of_band_resize_requires_reconciliation"
                    continue
                local.state, local.addresses, local.observed_at = remote.status, remote.addresses or {}, observed
                if not local.last_metered_at and remote.status == "ACTIVE":
                    local.last_metered_at = date(remote.launched_at) or observed
                    release(user, local)
                if local.last_metered_at:
                    settle(db, user, local, observed)
            project.last_collected_at, project.collection_error = observed, error
    except Exception as exc:
        log.warning("collection %s failed: %s", project_id, type(exc).__name__)
        with transaction() as db:
            project = db.get(Project, project_id)
            project.collection_error = "openstack_collection_failed"
    finally:
        if cloud:
            cloud.close()


def tick():
    for _ in range(20):
        if not run_operation():
            break
    with transaction() as db:
        projects = list(db.scalars(select(Project.id)))
    for ident in projects:
        collect_project(ident)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            tick()
        except Exception as exc:
            log.error("Worker tick failed: %s", type(exc).__name__)
            if args.once:
                raise
        if args.once:
            break
        time.sleep(settings().worker_interval_seconds)


if __name__ == "__main__":
    main()
