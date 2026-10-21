terraform {
  required_version = ">= 1.7, < 2.0"
  required_providers {
    grid = {
      source  = "threefoldtech/grid"
      version = "1.11.6"
    }
  }
}

provider "grid" {
  mnemonic = var.mnemonic
  network  = var.grid_network
}
