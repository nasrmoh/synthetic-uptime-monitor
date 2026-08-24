## Terraform `main.tf` Setup Notes

### What we built

We moved from the disposable Terraform resource-group exercise into the actual Azure infrastructure for the Synthetic Uptime Monitor.

Our current `main.tf` provisions the lower networking layer and the Linux VM.

The rough dependency structure is:

```text
Resource Group
    ↓
VNet
    ↓
Subnets
    ├── Application subnet
    ├── PostgreSQL subnet
    └── Private endpoint subnet

Application subnet
    ↓
NSG
    ↓
NIC
    ↓
Linux VM

Public IP
    ↓
NIC
```

Terraform determines most of this ordering automatically from references between resources.

For example:

```hcl
subnet_id = azurerm_subnet.app-subnet.id
```

tells Terraform that the NIC depends on the application subnet.

---

## Resource Group

We created one resource group to contain the project's Azure resources:

```text
synth-main-resource-group
```

Most other resources reference the resource group's name rather than hardcoding it.

This gives Terraform an implicit dependency on the resource group.

---

## VNet and Subnets

The VNet uses:

```text
172.16.0.0/16
```

We divided that address space into three `/24` subnets:

```text
172.16.1.0/24  application-subnet
172.16.2.0/24  postgresql-subnet
172.16.3.0/24  private-endpoint-subnet
```

### Application subnet

Reserved for the Linux VM.

The VM's NIC receives a private IP from this subnet.

Our first deployed VM received:

```text
172.16.1.4
```

### PostgreSQL subnet

Reserved for PostgreSQL Flexible Server using VNet integration.

We delegated it to:

```text
Microsoft.DBforPostgreSQL/flexibleServers
```

This lets Azure place the managed PostgreSQL service into the subnet later.

### Private endpoint subnet

Reserved for private endpoints, currently intended for managed Redis.

Nothing uses this subnet yet.

---

## Network Security Group

We created:

```text
synthetic-nsg
```

and associated it with the **application subnet**.

An NSG does not protect anything just because it exists. The subnet association is what makes its rules apply to network interfaces inside that subnet.

Azure automatically gives the NSG default rules, so we did not need to recreate them ourselves.

---

## VM Networking

The VM uses a Network Interface, or NIC.

Conceptually:

```text
VM
 ↓
NIC
 ↓
Application subnet
 ↓
VNet
```

The NIC has:

- a dynamically allocated private IP
    
- an associated static public IP
    

The public IP gives something on the Internet an address through which it can reach the NIC.

It does **not** automatically mean traffic is allowed through.

---

## Linux VM

We eventually provisioned:

```text
VM: synthetic-virtual-machine
Size: Standard_B2pts_v2
OS: Ubuntu 24.04 ARM64
Admin user: synth-admin
```

Password authentication is disabled.

Administrative login uses an SSH key:

```text
Local private key
        ↓
stays on our machine

Public key
        ↓
Terraform reads it
        ↓
installed on VM
```

Terraform also outputs:

```text
admin username
private IP
public IP
```

so we do not have to search through the Azure Portal for them after deployment.

---

# Issues We Ran Into

## 1. Azure policy restricted which regions we could use

Originally we attempted to deploy into:

```text
Canada Central
```

Azure rejected the VNet with:

```text
RequestDisallowedByAzure
```

This was not a Terraform configuration problem.

The Azure for Students subscription had an **Allowed resource deployment regions** policy.

We checked the policy and found that our subscription was limited to:

```text
westus3
southcentralus
mexicocentral
northcentralus
eastus2
```

We initially changed:

```text
Canada Central
```

to:

```text
East US 2
```

and the Terraform deployment then worked.

### Lesson

Terraform can only request resources that our Azure subscription is permitted to create.

A valid Terraform configuration can still fail because of Azure subscription policies.

---

# 2. `Standard_B1s` was unavailable in East US 2

When we later tried to create the VM in East US 2, Azure returned:

```text
SkuNotAvailable
```

The requested VM size was:

```text
Standard_B1s
```

The region itself was valid under our subscription policy, but Azure did not currently have capacity for that SKU there.

This was a different problem from the earlier region-policy failure.

```text
First failure:
Region prohibited by subscription policy

Second failure:
Region permitted, but requested VM SKU unavailable
```

We eventually moved the deployment to:

```text
North Central US
```

and selected:

```text
Standard_B2pts_v2
```

Because `B2pts_v2` is an ARM-based VM, we also selected the ARM64 Ubuntu image:

```text
Canonical
ubuntu-24_04-lts
server-arm64
```

### Lesson

There are several separate questions when selecting an Azure region:

```text
Does our subscription permit the region?
        ↓
Does the service exist there?
        ↓
Does the particular SKU exist there?
        ↓
Does Azure currently have capacity for it?
```

Passing one of those checks does not guarantee the next one.

---

# 3. The VM existed but SSH did not work

After Terraform successfully created the VM, we received:

```text
private IP: 172.16.1.4
public IP:  20.80.42.128
```

We then attempted to SSH into it.

Even though:

- the VM existed
    
- the public IP existed
    
- the NIC was correctly connected
    
- SSH was installed on the VM
    
- the correct public SSH key had been configured
    

port `22` was still unreachable.

The reason was the NSG.

Azure's default inbound rules eventually fall through to:

```text
DenyAllInBound
priority 65500
```

So our network path looked like:

```text
Laptop
   ↓
Public IP :22
   ↓
NIC
   ↓
Application subnet
   ↓
NSG
   X
default inbound deny
```

The public IP only provided an address.

It did **not** provide permission to reach the VM.

---

## Adding the SSH exception

We added a custom NSG rule allowing:

```text
Protocol: TCP
Direction: Inbound
Source: our public IP /32
Destination port: 22
Access: Allow
Priority: 100
```

Using `/32` restricts the source to exactly one IPv4 address.

So instead of:

```text
Internet → SSH → VM
```

we have:

```text
Our public IP
      ↓
TCP :22
      ↓
priority 100 Allow
      ↓
VM
```

Traffic from another Internet address does not match that rule and eventually reaches Azure's default inbound deny rule.

### Lesson

These are different concepts:

```text
Public IP
= where Internet traffic can address the resource

NSG
= whether that traffic is permitted

Port
= which application/service should receive the traffic
```

For SSH:

```text
Public IP
    ↓
NSG permits TCP 22
    ↓
VM
    ↓
sshd listening on port 22
```

All three pieces need to work.

---

# Current Port Policy

|Port|Who can reach it|Purpose|
|---|---|---|
|`22/TCP`|Our current public IP only|Temporary SSH administration|
|`80/TCP`|Not publicly allowed yet|Reserved for nginx HTTP later|
|`443/TCP`|Not publicly allowed yet|Reserved for nginx HTTPS later|
|`8000/TCP`|Never intentionally public|FastAPI internal application port|

The general approach is:

> Start with Azure's default inbound deny behaviour and add only the specific exceptions we can justify.

---

# Main Takeaways

The useful part of this setup was seeing that successfully creating a VM involves several independent layers:

```text
Terraform configuration
        ↓
Azure subscription policy
        ↓
regional/SKU availability
        ↓
VNet + subnet
        ↓
NIC + IP addresses
        ↓
NSG traffic rules
        ↓
VM
        ↓
service listening on a port
```

A failure at each layer looks different.

That is why an Azure VM being **successfully created** does not necessarily mean it is **reachable**, and a public IP does not necessarily mean a service is **publicly accessible**.

