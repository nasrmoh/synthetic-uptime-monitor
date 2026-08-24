# Terraform configuration.
# This block controls the Terraform CLI version and which providers
# this configuration depends on.
terraform {
  # "~> 1.15.0" means we expect Terraform 1.15.x.
  required_version = "~> 1.15.0"

  required_providers {
    # AzureRM is the provider Terraform uses to communicate with Azure.
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "=5.0.0"
    }
  }
}


# Configures the AzureRM provider.
# `features {}` is required by the provider even when we are not
# changing any provider-specific feature settings.
#
# Authentication is handled separately, such as through `az login`.
provider "azurerm" {
  features {}
}


# Resource group that contains the Azure resources for the project.
#
# `var.location` comes from variables.tf. This lets us change the
# deployment region without hardcoding it into every resource.
resource "azurerm_resource_group" "synth-resource-group" {
  name     = "synth-main-resource-group"
  location = var.location
}


# The VNet defines our project's overall private Azure network.
#
# 172.16.0.0/16 is the address space available to this VNet.
# We divide portions of this larger range into smaller subnets below.
resource "azurerm_virtual_network" "synth-vnet" {
  name          = "synthetic-vnet"
  location      = var.location
  address_space = ["172.16.0.0/16"]

  # Referencing the resource group's name creates an implicit dependency:
  # Terraform knows the resource group must exist before the VNet.
  resource_group_name = azurerm_resource_group.synth-resource-group.name
}


# Subnet reserved for the application VM.
#
# Later, the VM's network interface will join this subnet and receive
# a private IP from this address range, e.g. 172.16.1.x.
resource "azurerm_subnet" "app-subnet" {
  name                 = "application-subnet"
  resource_group_name  = azurerm_resource_group.synth-resource-group.name
  virtual_network_name = azurerm_virtual_network.synth-vnet.name

  # This subnet gets one smaller slice of the VNet's 172.16.0.0/16 space.
  address_prefixes = ["172.16.1.0/24"]
}


# Dedicated subnet for Azure Database for PostgreSQL Flexible Server.
#
# PostgreSQL uses VNet integration instead of a private endpoint,
# so Azure requires it to live inside a subnet delegated specifically
# to PostgreSQL Flexible Server.
resource "azurerm_subnet" "postgres-subnet" {
  name                 = "postgresql-subnet"
  resource_group_name  = azurerm_resource_group.synth-resource-group.name
  virtual_network_name = azurerm_virtual_network.synth-vnet.name
  address_prefixes     = ["172.16.2.0/24"]

  # Delegation tells Azure that this subnet is reserved for a particular
  # managed Azure service.
  delegation {
    name = "postgres-delegation"

    service_delegation {
      # Allow PostgreSQL Flexible Server to be integrated into this subnet.
      name = "Microsoft.DBforPostgreSQL/flexibleServers"

      # Permission required for the managed PostgreSQL service to join
      # the delegated subnet.
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action"
      ]
    }
  }
}


# Subnet reserved for private endpoints.
#
# Redis will eventually remain an Azure managed service outside the VNet,
# but its private endpoint can receive an IP from this subnet. That gives
# resources inside our VNet a private path to the managed Redis service.
resource "azurerm_subnet" "priv-endpoint-subnet" {
  name                 = "private-endpoint-subnet"
  resource_group_name  = azurerm_resource_group.synth-resource-group.name
  virtual_network_name = azurerm_virtual_network.synth-vnet.name
  address_prefixes     = ["172.16.3.0/24"]
}


# Network Security Group for the application subnet.
#
# An NSG acts like a network firewall. It controls which traffic is
# permitted to enter or leave resources protected by it.
#
# We currently define no custom rules. Azure automatically provides
# its default NSG rules, including denying unsolicited inbound traffic
# from the Internet.
resource "azurerm_network_security_group" "synth-network-security-group" {
  name                = "synthetic-nsg"
  location            = var.location
  resource_group_name = azurerm_resource_group.synth-resource-group.name
}


# Attach the NSG above to the entire application subnet.
#
# Creating an NSG alone does not make it protect anything. This association
# is what applies the NSG's rules to network interfaces in app-subnet.
#
# Later, when the VM's NIC joins app-subnet, the VM will therefore be
# subject to these NSG rules.
resource "azurerm_subnet_network_security_group_association" "app-subnet-synthetic-nsg-association" {
  subnet_id                 = azurerm_subnet.app-subnet.id
  network_security_group_id = azurerm_network_security_group.synth-network-security-group.id
}