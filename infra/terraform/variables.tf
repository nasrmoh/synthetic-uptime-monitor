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
  type        = bool
  description = "Whether or not we are bootstrapping the network"
  default     = false
}

variable "tailscale_ip" {
  type        = string
  description = "The IP for connecting to the private tailscale network"
}


variable "postgres_username" {
  type = string
}

variable "postgres_password" {
  type = string
}

variable "postgres_db_name" {
  type =string
}

variable "grafana_username"{
  type = string
}

variable "grafana_password" {
  type = string
}

variable "scheduler_enabled" {
  type = string
}


variable "linux_server_host"{
  type = string
}

variable "linux_server_user"{
  type = string
}

variable "redis_url" {
  type = string
}
