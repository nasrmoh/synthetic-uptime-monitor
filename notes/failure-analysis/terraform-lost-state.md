# Terraform Lost State

If we keep a disposable resource running, such as a virtual network inside a resource group, and then remove the local Terraform state file, `terraform plan` will indicate that the resource needs to be created again.

This happens because the state file is Terraform's memory of the resources it manages. It records the relationship between a Terraform resource address and the real Azure resource it corresponds to.

For example:

```text
azurerm_virtual_network.vnet
        ↓
Azure resource ID
        ↓
actual virtual network in Azure
```

If the state file is removed, Terraform loses that relationship.

The configuration still says that the virtual network should exist, but Terraform no longer has any state telling it that the existing Azure virtual network is the resource it already manages. Because of that, Terraform assumes it needs to create the resource.

Conceptually:

```text
Configuration:
Virtual network should exist

State:
No record of the virtual network

Azure:
Virtual network still exists
```

So `terraform plan` proposes creating the virtual network again.

If we then run `terraform apply`, Azure may reject the request because the resource already exists, or Terraform may create another resource if Azure allows it.

The important lesson is that Terraform state is what connects our configuration to the real infrastructure being managed. Losing state does not delete the Azure resource. It removes Terraform's knowledge that the resource already belongs to that configuration.
