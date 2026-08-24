output "public-ip" {
  description = "The public IP to reach our Virtual Machine"
  value       = azurerm_public_ip.public-ip.ip_address
}

output "private-ip" {
  description = "The private IP for our Virtual Machine"
  value       = azurerm_network_interface.vm-network-interface.private_ip_address
}

output "admin-username" {
  description = "The admin username for the Virtual Machine"
  value       = azurerm_linux_virtual_machine.synth-vm.admin_username
}

