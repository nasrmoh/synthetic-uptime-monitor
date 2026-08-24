terraform {
  required_version = "~> 1.15.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "=5.0.0"
    }
  }
}

provider "azurerm" {
  features {}
}


resource azurerm_resource_group "synth-resource-group"{
  name = "synth-main-resource-group"
  location = var.location
}