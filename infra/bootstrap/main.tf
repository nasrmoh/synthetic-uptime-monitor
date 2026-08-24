# Bootstrap Terraform configuration.
#
# This configuration exists only to create the Azure resources required
# to store the main Terraform configuration's remote state.
#
# It is intentionally separate from infra/terraform/ because the backend
# infrastructure must already exist before the main configuration can use it.
#
# This bootstrap configuration keeps its own Terraform state locally.
terraform {
  required_version = "~> 1.15.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "=5.0.0"
    }
  }
}


# Azure provider used to create the bootstrap resources.
provider "azurerm" {
  features {}
}


# Dedicated resource group for Terraform backend infrastructure.
#
# These resources are kept separate from the application's resource group
# because they should normally survive application infrastructure teardown.
resource "azurerm_resource_group" "boot-resource-group" {
  name     = "boostrap-resource-group"
  location = "North Central US"
}


# Storage account used to hold the main Terraform configuration's remote state.
resource "azurerm_storage_account" "boot-storage" {

  # Globally unique Azure Storage Account name.
  # Storage account names cannot contain hyphens or uppercase characters.
  name = "bootstrapstore"

  # Place this storage account inside the bootstrap resource group.
  # Referencing the resource group also creates an implicit Terraform dependency.
  resource_group_name = azurerm_resource_group.boot-resource-group.name

  # Deploy the storage account into the same Azure region as the bootstrap
  # resource group.
  location = azurerm_resource_group.boot-resource-group.location

  # Use Azure's Standard storage performance tier.
  # Terraform state is very small, so we do not need Premium storage.
  account_tier = "Standard"

  # LRS = Locally Redundant Storage.
  # Azure keeps multiple copies of the data within the region rather than
  # replicating it to another geographic region.
  account_replication_type = "LRS"

  # Hot is intended for data that is accessed relatively frequently.
  # Terraform reads and writes the state during operations such as plan/apply.
  access_tier = "Hot"

  # Settings that apply specifically to Blob Storage inside this account.
  blob_properties {

    # Keep previous versions of blobs when they are modified.
    #
    # Since our Terraform state will be stored as a blob, this gives us
    # previous state versions that may help with recovery if the current
    # state is accidentally overwritten or damaged.
    versioning_enabled = true
  }
}


# Private Blob container used by the main Terraform configuration as its
# azurerm backend.
#
# The main infrastructure's state blob, such as
# `synthetic-uptime-monitor.tfstate`, will be stored inside this container.
resource "azurerm_storage_container" "boot-storage-container" {
  name                  = "blob-container"
  storage_account_id    = azurerm_storage_account.boot-storage.id
  container_access_type = "private"
}