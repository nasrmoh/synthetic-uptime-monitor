## Automatically Generating the Ansible Inventory

Because we will repeatedly create and destroy the infrastructure while testing rebuilds from zero, Ansible needs a reliable way to discover information about the newly created VM.

For example, Ansible needs:

```text
VM host address
admin username
SSH private key
```

Our first approach was manual.

Terraform exposed values using outputs, and we manually copied those values into:

```text
ansible/inventory.yaml
```

This works, but it adds a manual step every time the VM is recreated.

A better approach is to let Terraform generate the Ansible inventory automatically.

### Inventory Template

We create a template file:

```text
terraform/templates/inventory.tftpl
```

with:

```yaml
webservers:
  hosts:
    synth_vm:
      ansible_host: ${vm_host}
      ansible_user: ${vm_username}
      ansible_ssh_private_key_file: ~/.ssh/synthetic_uptime_monitor_azure
```

The values:

```text
${vm_host}
${vm_username}
```

act as placeholders.

Terraform will substitute them with values from the infrastructure it creates.

### Generating `inventory.yaml`

Inside the main Terraform configuration, we use a `local_file` resource:

```hcl
resource "local_file" "ansible_inventory" {
  filename = "${path.module}/../ansible/inventory.yaml"

  content = templatefile("${path.module}/templates/inventory.tftpl", {
    vm_host     = azurerm_linux_virtual_machine.synth-vm.public_ip_address
    vm_username = azurerm_linux_virtual_machine.synth-vm.admin_username
  })
}
```

This does two things:

```text
templatefile()
→ fills in the template values

local_file
→ writes the generated result to inventory.yaml
```

`path.module` refers to the directory containing the current Terraform module.

This lets us build paths relative to the location of the Terraform configuration rather than depending on the directory from which Terraform was launched.

Now, whenever Terraform creates or updates the VM, it can also regenerate the Ansible inventory with the correct connection information.

---

# Automatically Detecting the Control Node's Public IP

During the bootstrap stage, SSH is exposed publicly, but only to the public IPv4 address of our control node.

The problem is that we may work from different networks, so this address can change.

Instead of manually updating Terraform each time, we can retrieve the current public IPv4 address during `terraform apply`.

We use:

```hcl
data "http" "ipv4" {
  url = "https://ipv4.icanhazip.com"
}

locals {
  my_ipv4 = chomp(data.http.ipv4.response_body)
}
```

The HTTP data source retrieves our current public IPv4 address.

`chomp()` removes the newline returned by the service.

We can then use that value in the NSG rule:

```hcl
source_address_prefix = "${local.my_ipv4}/32"
```

The `/32` means:

```text
allow exactly one IPv4 address
```

So during bootstrap, SSH is not open to the entire Internet.

Instead:

```text
Control node public IP
        ↓
TCP 22 allowed

Every other public IP
        ↓
blocked
```

---

# Initial Ansible Connectivity Test

Once Terraform has generated the inventory and the NSG allows our current public IP, we can verify that Ansible can reach the VM.

A successful Ansible ping looks like:

```text
synth_vm | SUCCESS => {
    "ansible_facts": {
        "discovered_interpreter_python": "/usr/bin/python3"
    },
    "changed": false,
    "ping": "pong"
}
```

This confirms that:

```text
Terraform generated the correct inventory
        +
Azure networking permits SSH
        +
SSH authentication works
        +
Ansible can execute commands on the VM
```

---

# Bootstrapping Automation

We eventually automated the entire transition from temporary public SSH access to steady-state administrative access through Tailscale.

The main script is:

```text
network-bootstrap.sh
```

The workflow happens in two stages.

---

## Stage 1: Bootstrap Using Public SSH

We first enable Terraform's bootstrap mode.

While bootstrap mode is enabled, Terraform:

- creates the temporary NSG rule allowing SSH from the control node's current public IPv4 address
    
- creates the VM
    
- generates the Ansible inventory
    
- places the VM's Azure public IP into `ansible_host`
    

At this point the connection path is:

```text
Control node
    ↓
Internet
    ↓
Azure public IP
    ↓
TCP 22
    ↓
VM
```

This public SSH path exists only because Tailscale has not been installed yet.

### Running the Bootstrap Playbook

The script then runs:

```text
playbook_boot.yaml
```

This playbook:

- installs Tailscale on the VM
    
- authenticates the VM with our existing tailnet
    
- retrieves the VM's Tailscale IPv4 address
    
- prints the address through Ansible output
    

Conceptually:

```text
Terraform
    ↓
create VM
    ↓
temporary public SSH
    ↓
Ansible connects through public IP
    ↓
playbook_boot.yaml
    ↓
install Tailscale
    ↓
join tailnet
    ↓
retrieve Tailscale IP
```

The bootstrap script captures this output and extracts the Tailscale IPv4 address.

---

# Verifying Tailscale Before Removing Public SSH

Before removing the public SSH path, we verify that the VM is actually reachable through Tailscale.

This is important because otherwise we could remove public SSH before confirming that the replacement connection works.

The transition should therefore be:

```text
Public SSH works
        ↓
Install Tailscale
        ↓
Discover Tailscale IP
        ↓
Verify Tailscale connectivity
        ↓
Only then remove public SSH
```

This prevents us from accidentally locking ourselves out of the VM.

---

# Stage 2: Transition to Steady State

Once Tailscale has been verified, the script stores the discovered Tailscale address for Terraform and disables bootstrap mode.

Terraform is then applied again.

Because the public SSH NSG rule only exists while bootstrap mode is enabled, Terraform removes that rule.

The VM still keeps its Azure public IP.

We are only removing:

```text
public administrative SSH access
```

The public IP will later be used for application traffic through nginx on ports such as:

```text
80
443
```

Terraform also regenerates the Ansible inventory.

Instead of:

```text
ansible_host = Azure public IP
```

it now uses:

```text
ansible_host = Tailscale IP
```

The administrative connection path becomes:

```text
Control node
    ↓
Tailscale private network
    ↓
VM Tailscale IP
    ↓
OpenSSH
    ↓
Ansible
```

---

# Running the Main Ansible Configuration

Once the inventory points to the Tailscale address, the script runs the main Ansible playbook.

This configures the rest of the VM, including:

```text
Docker
Docker Compose
application users and groups
deployment directories
permissions
application configuration
monitoring configuration
nginx
Certbot
```

All later Ansible connections use Tailscale rather than the VM's public SSH interface.

---

# Overall Bootstrap Flow

The complete process is:

```text
Bootstrap mode enabled
        ↓
Terraform determines current control-node IPv4
        ↓
Terraform allows temporary SSH from that /32 address
        ↓
Terraform creates VM
        ↓
Terraform generates inventory using Azure public IP
        ↓
Ansible connects over public SSH
        ↓
playbook_boot.yaml installs Tailscale
        ↓
VM joins tailnet
        ↓
script retrieves Tailscale IPv4 address
        ↓
Tailscale connectivity is verified
        ↓
bootstrap mode disabled
        ↓
Terraform runs again
        ↓
public SSH ingress rule is removed
        ↓
Terraform regenerates inventory using Tailscale IP
        ↓
Ansible reconnects through Tailscale
        ↓
main configuration playbook runs
```

The main result is that public SSH exists only long enough to bootstrap the machine.

After Tailscale is installed and verified:

```text
Administrative access
→ Tailscale

Public application traffic
→ Azure public IP
→ nginx
→ HTTP/HTTPS
```

This lets us repeatedly destroy and recreate the VM without manually editing the Ansible inventory or permanently exposing SSH to the public Internet.