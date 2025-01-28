terraform {
  required_providers {
    linode = {
      source  = "linode/linode"
      version = "~> 2.0"
    }
  }
}

provider "linode" {
  token = var.linode_token
}

# US East Cluster
module "lke_us_east" {
  source = "./modules/lke-cluster"

  cluster_name    = "event-processor-us-east"
  region         = "us-east"
  k8s_version    = var.kubernetes_version
  node_pools     = var.node_pools
  tags           = ["production", "us-east"]
}

# EU West Cluster
module "lke_eu_west" {
  source = "./modules/lke-cluster"

  cluster_name    = "event-processor-eu-west"
  region         = "eu-west"
  k8s_version    = var.kubernetes_version
  node_pools     = var.node_pools
  tags           = ["production", "eu-west"]
}

# AP South Cluster
module "lke_ap_south" {
  source = "./modules/lke-cluster"

  cluster_name    = "event-processor-ap-south"
  region         = "ap-south"
  k8s_version    = var.kubernetes_version
  node_pools     = var.node_pools
  tags           = ["production", "ap-south"]
}
