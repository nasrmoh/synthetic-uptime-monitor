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