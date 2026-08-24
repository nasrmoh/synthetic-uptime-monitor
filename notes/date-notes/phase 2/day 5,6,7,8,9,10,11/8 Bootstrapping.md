## Terraform State

Terraform state is Terraform's record of the infrastructure it manages.

It connects Terraform resources such as:

```text
azurerm_linux_virtual_machine.synth-vm
```

to the real Azure resources they represent.

When we run `terraform plan`, Terraform considers:

```text
Configuration
= what we want

State
= what Terraform knows it manages

Azure
= what actually exists
```

If state is lost, Terraform loses these resource mappings. Even if the infrastructure still exists in Azure, Terraform may propose creating it again because it no longer knows that it manages the existing resources.

---

## Why Store State Remotely?

Originally, our state existed only as a local:

```text
terraform.tfstate
```

Losing that file would mean losing Terraform's record of our infrastructure.

We also do not want to commit state to Git because it can contain sensitive infrastructure information and changes frequently.

Instead:

```text
GitHub
→ Terraform configuration

Azure Blob Storage
→ Terraform state
```

Our main Terraform configuration therefore stores its state remotely in Azure Blob Storage.

---

## Bootstrapping

There is a chicken-and-egg problem with remote state.

We want Terraform to store its state in Azure Storage, but the storage account and container must already exist before Terraform can use them as a backend.

```text
Main Terraform
needs
    ↓
Azure Storage backend

but

Azure Storage backend
must exist first
```

To solve this, we use a separate bootstrap configuration:

```text
infra/
├── bootstrap/
└── terraform/
```

The bootstrap configuration creates only:

```text
Resource Group
    ↓
Storage Account
    ↓
Blob Container
```

The main Terraform configuration then uses that Blob container to store the state for our VM, networking, and other application infrastructure.

```text
Bootstrap Terraform
        ↓
creates remote-state storage
        ↓
Main Terraform
        ↓
stores state remotely
        ↓
manages application infrastructure
```

---

## Bootstrap State

The bootstrap configuration keeps its own `terraform.tfstate` locally and gitignored.

This means:

```text
bootstrap/
→ local state

terraform/
→ remote state in Azure Blob Storage
```

We accept local state for bootstrap because it manages only a few small and stable resources.

If bootstrap state were lost, Terraform would forget that it manages the resource group, storage account, and container. We could recover these few resources using `terraform import`.

The bootstrap infrastructure should normally remain running because its Blob container holds the main infrastructure's Terraform state.

---

## AzureRM Backend

We add an `azurerm` backend block to the main Terraform configuration.

Its job is to tell Terraform where the main configuration should read and write its state.

Conceptually:

```text
azurerm backend
    ↓
Bootstrap Resource Group
    ↓
Storage Account
    ↓
Blob Container
    ↓
synthetic-uptime-monitor.tfstate
```

When we migrated from local state, `terraform init -migrate-state` copied our existing state into this remote backend while preserving Terraform's existing resource mappings.