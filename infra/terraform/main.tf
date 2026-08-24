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
  # Store this configuration's Terraform state remotely in Azure Blob Storage.
  #
  # The resource group, storage account, and container are created separately
  # by the bootstrap Terraform configuration. They must already exist before
  # this backend can be initialized.
  #
  # `key` is the name of the blob that holds this configuration's state.
  backend "azurerm" {
    resource_group_name  = "bootstrap-resource-group"
    storage_account_name = "bootstrapstore"
    container_name       = "blob-container"
    key                  = "synthetic-uptime-monitor.tfstate"
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
# Network interface (NIC) for the application VM.
#
# The VM does not connect directly to the VNet. Its NIC is the network-facing
# component that joins a subnet and receives IP addressing.
#
# Conceptually:
#
# VM -> NIC -> application-subnet -> VNet
resource "azurerm_network_interface" "vm-network-interface" {
  name                = "vm-net-interface"
  resource_group_name = azurerm_resource_group.synth-resource-group.name
  location            = var.location

  ip_configuration {
    name = "nic-ip"

    # Places this NIC inside the application subnet.
    #
    # This reference also creates an implicit dependency on app-subnet:
    # Terraform cannot create the NIC until the subnet exists.
    subnet_id = azurerm_subnet.app-subnet.id

    # Azure automatically assigns the NIC a private IP from the
    # application's 172.16.1.0/24 subnet.
    #
    # Our first deployment received 172.16.1.4.
    private_ip_address_allocation = "Dynamic"

    # Associates our separate Azure Public IP resource with this NIC.
    #
    # This gives Internet traffic an address through which it can reach
    # the NIC. Whether that traffic is actually allowed is still controlled
    # by the NSG.
    public_ip_address_id = azurerm_public_ip.public-ip.id
  }
}


# Linux VM that will eventually run the containerized application and
# observability services.
#
# Terraform creates the VM itself here, while networking is supplied through
# the NIC created above.
resource "azurerm_linux_virtual_machine" "synth-vm" {
  name                = "synthetic-virtual-machine"
  resource_group_name = azurerm_resource_group.synth-resource-group.name
  location            = var.location

  # ARM-based B-series VM selected after Standard_B1s was unavailable
  # because of Azure capacity restrictions.
  size = "Standard_B2pts_v2"

  # Linux user used for administrative SSH access.
  admin_username = "synth-admin"

  # Attach the NIC to the VM.
  #
  # This creates another implicit dependency:
  #
  # subnet -> NIC -> VM
  network_interface_ids = [
    azurerm_network_interface.vm-network-interface.id
  ]

  # Do not permit password-based SSH authentication.
  # Administrative access must instead use the SSH key below.
  disable_password_authentication = true


  # Install our SSH public key for the administrative user.
  #
  # The private key stays on our local machine and is never supplied
  # to Terraform or Azure.
  admin_ssh_key {
    # var.ssh_public_key_path contains the local path to our .pub file.
    #
    # pathexpand() expands "~" to our home directory.
    # file() then reads the contents of that public-key file.
    public_key = file(pathexpand(var.ssh_public_key_path))
    username   = "synth-admin"
  }


  # Operating-system disk for the VM.
  os_disk {
    # ReadWrite allows normal reads and writes to use host caching.
    caching = "ReadWrite"

    # Standard Azure managed SSD storage for the VM's OS disk.
    storage_account_type = "StandardSSD_LRS"

    # 64 GiB OS disk.
    disk_size_gb = 64
  }


  # Defines the base operating-system image Azure should use when creating
  # the VM.
  #
  # B2pts_v2 is an ARM64 VM size, so the Ubuntu ARM64 image is used.
  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server-arm64"

    # Use the latest available version of this Ubuntu 24.04 ARM64 image.
    version = "latest"
  }
}


# Public IPv4 address associated with the VM's NIC.
#
# The Public IP and the VM are separate Azure resources.
#
# Conceptually:
#
# Internet
#    ↓
# Public IP
#    ↓
# NIC
#    ↓
# VM
resource "azurerm_public_ip" "public-ip" {
  name                = "main-public-ip"
  resource_group_name = azurerm_resource_group.synth-resource-group.name
  location            = var.location

  # Static means the allocated public IP remains associated with this
  # Public IP resource rather than changing dynamically.
  allocation_method = "Static"

  # Standard is Azure's current production-oriented Public IP SKU.
  sku = "Standard"
}


# Custom NSG rule permitting administrative SSH access to the VM.
#
# Azure's default NSG rules ultimately deny unsolicited inbound Internet
# traffic. This rule creates one narrow exception for SSH from our own
# current public IP address.
resource "azurerm_network_security_rule" "ssh-security-rule" {
  name = "ssh-inbound-security"

  # Traffic matching this rule is permitted.
  access = "Allow"

  # Lower numbers are evaluated before higher numbers.
  #
  # Custom rule 100 therefore takes precedence over Azure's default
  # DenyAllInBound rule at priority 65500.
  priority = 100

  # This rule applies to traffic entering the protected subnet.
  direction = "Inbound"

  # SSH operates over TCP.
  protocol = "Tcp"

  # Add this rule to our existing application NSG.
  resource_group_name         = azurerm_resource_group.synth-resource-group.name
  network_security_group_name = azurerm_network_security_group.synth-network-security-group.name


  # Only allow traffic originating from this one public IPv4 address.
  #
  # /32 represents exactly one IPv4 address rather than an address range.
  #
  # This prevents SSH from being exposed to the entire Internet.
  source_address_prefix = "104.205.205.169/32"

  # The SSH client uses an ephemeral source port, so we do not restrict it.
  source_port_range = "*"


  # The NSG is already associated specifically with the application subnet,
  # so we do not need to restrict this rule to one particular destination
  # IP here.
  destination_address_prefix = "*"

  # SSH server listens on TCP port 22.
  destination_port_range = "22"
}