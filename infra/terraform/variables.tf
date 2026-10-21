variable "mnemonic" {
  description = "Operator wallet: export TF_VAR_mnemonic; state must be private."
  type        = string
  sensitive   = true
  nullable    = false
}

variable "grid_network" {
  type    = string
  default = "main"
  validation {
    condition     = contains(["main", "test", "qa", "dev"], var.grid_network)
    error_message = "Grid network must be main, test, qa, or dev. Testnet can still consume resources."
  }
}

variable "name" {
  type    = string
  default = "nebula"
  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,23}$", var.name))
    error_message = "Use a short lowercase alphanumeric/underscore deployment name."
  }
}

variable "network_cidr" {
  type    = string
  default = "10.42.0.0/16"
  validation {
    condition     = can(cidrhost(var.network_cidr, 1)) && endswith(var.network_cidr, "/16")
    error_message = "The Grid provider requires a /16 network."
  }
}

variable "ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) ", trimspace(var.ssh_public_key)))
    error_message = "Supply an OpenSSH public key, never a private key."
  }
}

variable "ubuntu_flist" {
  description = "Verified Ubuntu 24.04 full-VM flist containing an EFI/cloud-init boot disk."
  type        = string
  validation {
    condition     = startswith(var.ubuntu_flist, "https://")
    error_message = "Use an HTTPS full-VM image reference."
  }
}

variable "ubuntu_flist_checksum" {
  description = "Verified flist checksum accepted by the Grid provider; never guess it."
  type        = string
  validation {
    condition     = can(regex("^[a-fA-F0-9]{32,128}$", var.ubuntu_flist_checksum))
    error_message = "Supply the real image checksum."
  }
}

variable "controllers" {
  type = map(object({
    node_id     = number
    cpu         = optional(number, 4)
    memory_mb   = optional(number, 16384)
    disk_gb     = optional(number, 100)
    public_ipv4 = optional(bool, false)
  }))
  validation {
    condition     = contains([1, 3], length(var.controllers))
    error_message = "Supply one pilot controller or three HA-candidate controllers."
  }
}

variable "computes" {
  description = "Empty only for the initial approved preflight deployment."
  type = map(object({
    node_id     = number
    cpu         = optional(number, 8)
    memory_mb   = optional(number, 32768)
    disk_gb     = optional(number, 200)
    public_ipv4 = optional(bool, false)
  }))
  default = {}
}
