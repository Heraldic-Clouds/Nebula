locals {
  hosts = merge(
    { for name, node in var.controllers : "controller_${name}" => merge(node, { role = "control" }) },
    { for name, node in var.computes : "compute_${name}" => merge(node, { role = "compute" }) }
  )
}

resource "grid_network" "management" {
  name          = "${var.name}_management"
  description   = "Nebula private WireGuard transport; not a Neutron provider network"
  nodes         = distinct([for host in local.hosts : host.node_id])
  ip_range      = var.network_cidr
  add_wg_access = true
}

resource "grid_deployment" "host" {
  for_each     = local.hosts
  name         = "${var.name}_${each.key}"
  node         = each.value.node_id
  network_name = grid_network.management.name

  disks {
    name = "${each.key}_root"
    size = each.value.disk_gb
  }

  vms {
    name           = each.key
    flist          = var.ubuntu_flist
    flist_checksum = var.ubuntu_flist_checksum
    cpu            = each.value.cpu
    memory         = each.value.memory_mb
    publicip       = each.value.public_ipv4
    planetary      = false
    # Full VM boot disk; ThreeFold copies /image.raw to this first disk.
    mounts {
      name        = "${each.key}_root"
      mount_point = "/"
    }
    env_vars = {
      SSH_KEY = trimspace(var.ssh_public_key)
    }
  }

  lifecycle {
    precondition {
      condition     = each.value.node_id > 0 && each.value.cpu >= 1 && each.value.cpu <= 32 && each.value.disk_gb >= 40
      error_message = "Select real node IDs and valid CPU/disk capacities before planning."
    }
  }
}
