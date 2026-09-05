# Full Infrastructure Run

### 1. Bootstrap Terraform State Infrastructure

First, we go to:

```text
infra/bootstrap
```

This directory contains the separate Terraform configuration used to create the remote state infrastructure.

Its purpose is to provision the Azure Blob Storage resources that the main Terraform configuration uses as its backend.

From this directory, we run:

```bash
terraform apply
```

This creates the storage resources required to hold the main Terraform state.

### 2. Run the Network Bootstrap Script

After the backend infrastructure exists, we return to the repository root and run the network bootstrap script.

The script begins by running the main Terraform configuration.

We review the Terraform plan and approve it.

Terraform then creates the main Azure infrastructure, including the VM and the temporary public SSH access required for initial configuration.

### 3. Establish the Initial SSH Connection

Once the VM is created, Ansible connects to it through the VM's public IP address.

Because this is a newly created VM with a new SSH host key, SSH may prompt us to confirm that we trust the machine we are connecting to.

After the connection succeeds, the bootstrap Ansible playbook installs and configures Tailscale on the VM.

At this stage, the VM temporarily has:

```text
Public SSH access
        +
Tailscale access
```

### 4. Remove Public SSH Access

After Tailscale has been installed and verified, Terraform runs again.

We review and approve the second Terraform plan.

This second apply removes the temporary public SSH rule.

The intended steady-state access path is now:

```text
Control node
    ↓
Tailscale
    ↓
Azure VM
```

instead of SSH over the public Internet.

### 5. Configure the VM with Ansible

Ansible then connects to the VM again, this time through its Tailscale address.

The main configuration playbook finishes setting up the server.

This includes:

- installing Docker
    
- installing Docker Compose
    
- creating the application users and groups
    
- creating `/opt/synthetic-uptime-monitor`
    
- applying the required file and directory permissions
    
- copying the deployment Compose file
    
- copying the `.env` file
    
- copying Prometheus, Grafana, and Alertmanager configuration
    
- copying `prometheus.yml`
    
- pulling the required container images, including the application image from GHCR
    
- installing nginx
    
- installing Certbot
    

The overall flow is therefore:

```text
Terraform bootstrap
    ↓
Azure Blob Storage for remote state
    ↓
network-bootstrap.sh
    ↓
main Terraform apply
    ↓
Azure infrastructure + temporary public SSH
    ↓
Ansible bootstrap
    ↓
install and verify Tailscale
    ↓
second Terraform apply
    ↓
remove public SSH access
    ↓
Ansible over Tailscale
    ↓
fully configure the VM
```

This gives us a reproducible path from an empty Azure environment to a configured deployment VM using Terraform for infrastructure and Ansible for machine configuration.