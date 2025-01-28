variable "linode_token" {
  description = "Linode API token"
  type        = string
  sensitive   = true
}

variable "kubernetes_version" {
  description = "Kubernetes version for LKE clusters"
  type        = string
  default     = "1.28"
}

variable "node_pools" {
  description = "Configuration for node pools"
  type = list(object({
    type  = string
    count = number
    tags  = list(string)
  }))
  default = [
    {
      type  = "g6-standard-2"
      count = 3
      tags  = ["production"]
    }
  ]
}
