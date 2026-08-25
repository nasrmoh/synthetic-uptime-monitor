## Infrastructure Rebuild Rehearsal

We first ran `terraform plan` against the main Terraform configuration and confirmed that the deployed infrastructure matched our configuration.

`terraform state list` showed the following managed resources:

```text
azurerm_linux_virtual_machine.synth-vm
azurerm_network_interface.vm-network-interface
azurerm_network_security_group.synth-network-security-group
azurerm_network_security_rule.ssh-security-rule
azurerm_public_ip.public-ip
azurerm_resource_group.synth-resource-group
azurerm_subnet.app-subnet
azurerm_subnet.postgres-subnet
azurerm_subnet.priv-endpoint-subnet
azurerm_subnet_network_security_group_association.app-subnet-synthetic-nsg-association
azurerm_virtual_network.synth-vnet
```

Before destruction, our Terraform outputs were:

```text
admin-username = "synth-admin"
private-ip     = "172.16.1.4"
public-ip      = "20.80.42.128"
```

## Destroy and Rebuild

We then ran:

```bash
terraform destroy
```

This removed everything managed by the **main Terraform configuration**, while leaving the separate bootstrap infrastructure and remote state backend intact.

We then ran:

```bash
terraform apply
```

Terraform was able to recreate the entire infrastructure from the configuration.

Running:

```bash
terraform plan
```

afterwards reported no changes, confirming that the rebuilt infrastructure matched our desired configuration.

`terraform state list` also contained the same set of Terraform resources as before the destruction.

## Values That Changed

After rebuilding, the outputs were:

```text
admin-username = "synth-admin"
private-ip     = "172.16.1.4"
public-ip      = "130.131.52.135"
```

The administrator username and private IP remained the same, but the public IP changed:

```text
Before: 20.80.42.128
After:  130.131.52.135
```

Although the Public IP resource uses static allocation, destroying that resource releases the address. When Terraform creates a new Public IP resource during the rebuild, Azure can assign a different address.

## Verifying the Rebuilt VM

We SSHed into the recreated VM using the new public IP address and confirmed that it was reachable.

Because this was a newly created VM and the previous OS disk had been destroyed, software installed manually on the old VM was also gone.

For example:

```text
Old VM
├── Docker installed manually
└── GHCR application image pulled locally

terraform destroy
        ↓

VM + OS disk destroyed
        ↓

terraform apply
        ↓

New VM + new OS disk
├── Docker not installed
└── GHCR image not present
```

This demonstrates an important boundary in our Terraform configuration: **Terraform can currently reproduce the Azure infrastructure, but it does not yet reproduce the software configuration inside the VM.**

That later becomes the job of our VM configuration/deployment layer.
