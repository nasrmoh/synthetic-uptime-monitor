variable "location" {
  type        = string
  description = "Location for our Azure Resources"
  default     = "North Central US"
}


variable "ssh_public_key_path" {
  type        = string
  description = "Path to the public SSH key used for VM administration"
  default     = "~/.ssh/synthetic_uptime_monitor_azure.pub"
}


variable "bootstrap_mode" {
  type = bool
  description = "Whether or not we are bootstrapping the network"
  default = false
}

variable "tailscale_ip" {
  type = string
  description = "The IP for connecting to the private tailscale network"
  default = "10.10.10.10"
}