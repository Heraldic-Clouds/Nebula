output "hosts" {
  description = "Non-secret inventory input; role mappings do not imply preflight success."
  value = { for name, host in grid_deployment.host : name => {
    role        = local.hosts[name].role
    node_id     = local.hosts[name].node_id
    contract_id = host.id
    address     = host.vms[0].ip
    public_ipv4 = host.vms[0].computedip
  } }
}

output "wireguard_config" {
  value     = grid_network.management.access_wg_config
  sensitive = true
}
