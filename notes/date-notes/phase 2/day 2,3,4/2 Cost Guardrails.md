# Cost Guardrails

We currently have access to two Azure subscriptions:

- a personal Azure account, previously used for services such as Microsoft Text to Speech
    
- an Azure for Students account, created May 8, 2026
    

For this project, the Azure for Students subscription is the better development environment.

It includes a fixed **$100 USD credit**, approximately **$136.90 CAD**, and does not require a credit card. If the available credit is exhausted, the subscription is disabled instead of continuing to accumulate charges.

The personal Azure account does not provide the same protection. Misconfigured or forgotten resources could continue generating charges. Since Phase 2 involves experimenting with unfamiliar Azure services, the automatic spending boundary of the student subscription is valuable.

The main disadvantage is that the student subscription will eventually expire. Moving the deployment to the personal Azure account may require recreating infrastructure and configuration.

That migration is acceptable because Terraform, Ansible, and the deployment documentation should make the environment reproducible rather than dependent on remembering manual setup steps.

## Decision

Use the **Azure for Students subscription** for development and the initial Azure deployment.

Maintain documentation covering:

- Azure resources created
    
- architecture and configuration decisions
    
- resource lifecycle procedures
    
- networking configuration
    
- Terraform bootstrap steps
    
- any remaining manual Azure configuration
    

This documentation, together with Terraform and Ansible, should make a future migration to the personal subscription repeatable.

## Budget Alerts

An Azure budget has been created at the CAD equivalent of the $100 USD credit:

**$136.90 CAD**

Alerts are configured at:

- 25%
    
- 50%
    
- 75%
    
- 95%
    
- 100%
    

Notifications are sent to both the university and personal email accounts.

The goal is to detect unexpected spending well before the student credit is exhausted.

---

# Cost Model

ADR-003 established that cost is an architectural constraint rather than something considered after deployment.

## Revised Strategy: Keep Free-Tier Resources Standing, Cycle Paid Resources

The original development model was:

> provision resources when working, then tear them down afterward.

After reviewing the Azure for Students allowances, that model no longer makes sense for every resource.

The more useful distinction is:

> **Does this resource have a durable no-cost allowance that makes leaving it provisioned simpler than repeatedly rebuilding it?**

If yes, it belongs in the **standing infrastructure**.

If not, and the resource can be recreated without losing important state, it belongs in the **session infrastructure**.

This changes the earlier assumptions around both the VM and PostgreSQL.

### Standing Infrastructure

Provision once and normally leave running:

- Terraform state storage
    
- VNet
    
- subnet
    
- NSG
    
- private DNS zones
    
- Azure Container Registry, pending confirmation of the subscription-specific free allowance
    
- Linux VM
    
- VM managed disk
    
- static public IP
    
- PostgreSQL Flexible Server
    
- PostgreSQL private endpoint
    

### Session Infrastructure

Provision only when required and destroy afterward:

- managed Redis
    
- Redis private endpoint
    
- Redis private DNS zone-group link
    

Redis is therefore the main remaining create/prove/destroy resource.

---

# Confirmed Free-Tier Assumptions

|Resource|Allowance|Duration|Important constraint|
|---|--:|---|---|
|Linux VM, B1s|750 hours/month|Recurring|One continuously running VM fits just below the monthly allowance|
|VM managed disk|Included|Recurring|Must use the qualifying P6 64 GiB Premium SSD SKU|
|PostgreSQL Flexible Server, B1ms|750 hours/month + 32 GB storage + 32 GB backup|12 months from account creation|Expected to expire around May 8, 2027|
|Azure Container Registry|1 Standard registry, 100 GB storage, 10 webhooks|Listed as Always|Still needs confirmation against this subscription|
|Static public IP|One qualifying IP attached to the free-tier VM|Tied to VM allowance|No separate standing charge while qualifying|
|Managed Redis|None identified|N/A|Paid while provisioned|
|Private endpoints|None identified|N/A|Paid per endpoint while provisioned|

---

# Consequences of Keeping PostgreSQL Standing

Moving PostgreSQL back into the standing tier simplifies several parts of the system.

## Seed Data

The seed script becomes a **one-time bootstrap step**, not something run every working session.

Target definitions persist naturally in PostgreSQL.

## Check History

Check-result history can accumulate over time.

This makes longer-running Grafana queries and alert behaviour more representative because data does not reset every session.

## Database Migrations

The initial Alembic migration runs during bootstrap.

Future schema changes continue through normal Alembic migrations, but the database itself does not need to be reconstructed every time development resumes.

## Backup and Restore

The later backup/restore exercise becomes meaningful again because PostgreSQL contains accumulated application data rather than disposable seeded state.

## Ansible

The VM is also standing, so the Ansible playbook becomes a configuration-convergence tool rather than something that must rebuild the server every day.

The periodic rebuild exercises still matter because they prove the infrastructure remains reproducible.

---

# Per-Resource Cost Model

## Linux VM — Standing

Initial VM:

**Standard B1s**

- 1 vCPU
    
- 1 GiB RAM
    
- 10% base CPU performance with burst capability
    
- P6 64 GiB Premium SSD
    
- maximum 320 IOPS
    
- 4 GiB temporary storage
    

The Azure for Students allowance provides approximately:

**750 VM hours/month**

A single VM running continuously consumes approximately 720 to 744 hours depending on the month, leaving only a small margin.

This means overlapping VMs should be avoided unless intentionally testing a migration or rebuild.

### Lifecycle

```text
provision once
    ↓
leave running
    ↓
periodic deliberate rebuild drills
```

The VM is no longer expected to be destroyed or deallocated after every working session.

---

## PostgreSQL Flexible Server — Standing, Time-Bounded

Initial target:

**B1ms**

Current student allowance:

- 750 compute hours/month
    
- 32 GB database storage
    
- 32 GB backup storage
    

The important limitation is duration.

The allowance is available for approximately **12 months from account creation**, which places the expected end around:

**May 8, 2027**

Storage must remain below the free allowance.

Automatic storage growth needs to be monitored because exceeding the free allocation can move the database into paid storage.

Once the free allowance expires, the current rough estimate is:

- **~$25 CAD/month compute**
    
- **~$5 CAD/month storage**
    

### Lifecycle

```text
provision once
    ↓
run Alembic migrations
    ↓
seed initial targets
    ↓
leave running
    ↓
revisit before May 2027
```

Before the free period expires, decide whether to:

- begin paying normal PostgreSQL costs
    
- return to a teardown/reseed model
    
- migrate the database elsewhere
    

---

## Managed Redis — Session

Managed Redis does not currently have a useful student free-tier allowance.

Estimated continuous cost:

**~$13 CAD/month**

Because Redis contains disposable operational state rather than durable application data, it remains the cleanest candidate for ephemeral provisioning.

### Lifecycle

```text
need managed Redis
    ↓
provision Redis
    +
private endpoint
    +
DNS zone-group link
    ↓
test integration
    ↓
capture evidence
    ↓
destroy Redis and related endpoint resources
```

This allows the project to gain experience with managed Redis without paying to leave it unused.

---

## Azure Container Registry — Standing, Pending Confirmation

ACR stores versioned Docker images used by the deployment.

Microsoft documentation currently lists an Azure for Students allowance that includes:

- one Standard registry
    
- 100 GB of storage
    
- 10 webhooks
    

This still needs to be confirmed against the actual subscription before treating the previous **~$7 CAD/month** estimate as irrelevant.

If the allowance applies, ACR can remain standing at no additional cost while usage stays within the limits.

If it does not apply, the previous estimate remains:

**~$7 CAD/month**

GitHub Container Registry and Docker Hub remain possible alternatives, although using ACR provides more Azure-specific deployment experience.

---

## Terraform State Storage — Standing

Terraform remote state will live in Azure Blob Storage.

Its storage requirements are extremely small.

Expected cost outside the student allowance:

**~$0.25 CAD/month**

This resource should remain provisioned continuously because Terraform needs its state to understand which infrastructure it manages.

### Lifecycle

```text
create once
    ↓
store remote Terraform state
    ↓
leave provisioned
```

---

# Networking

## PostgreSQL Private Endpoint — Standing

The PostgreSQL private endpoint remains provisioned because PostgreSQL itself is now standing.

Estimated cost:

**~$10 CAD/month**, plus a small amount for data processing.

This is currently the clearest unavoidable standing cost in the architecture.

Its associated private DNS configuration should remain available for as long as the database and endpoint exist.

---

## Redis Private Endpoint — Session

The Redis private endpoint follows Redis's lifecycle.

### Lifecycle

```text
create Redis
    +
create private endpoint
    +
attach DNS zone-group
    ↓
test
    ↓
destroy all three
```

The first implementation should verify several assumptions rather than relying on them.

|Area|What to verify|
|---|---|
|Private DNS cleanup|Whether Terraform removes the DNS zone-group configuration cleanly|
|Private IP stability|Whether recreation assigns a different private IP|
|Dependency ordering|Whether normal `apply` and `destroy` correctly handle the dependency chain|
|Rebuild reliability|Whether DNS and application connectivity return without manual intervention|

Downstream configuration should reference the **private DNS hostname**, not the private IP address.

That prevents Redis configuration from breaking if Azure assigns a different private IP after recreation.

---

## Private DNS Zones — Standing

The private DNS zones themselves remain part of the standing network foundation.

Examples include the zones used for managed PostgreSQL and Redis private connectivity.

They are separate from the endpoints themselves and should not need to be destroyed whenever Redis is cycled.

---

## Static Public IP — Standing

The static public IP remains attached to the standing VM.

Under the current free-tier assumptions, that avoids the previous concern about deleting and recreating the IP between sessions.

It also makes later DNS configuration much simpler because the application's public address remains stable.

Once a domain is configured, its A record can continue pointing at the same IP.

---

## Shared Outbound Data Allowance

The **100 GB/month outbound allowance is shared across the subscription**.

It is not separate for the VM and ACR.

Traffic contributing to the same allowance includes:

- package downloads
    
- Docker image pulls
    
- Tailscale traffic
    
- Certbot communication
    
- synthetic HTTP checks
    
- GitHub Actions / ACR deployment traffic where applicable
    

Conceptually:

```text
VM traffic ──────────────┐
                         │
container traffic ───────┼──> shared 100 GB/month allowance
                         │
other Azure egress ──────┘
```

Current project usage is expected to remain well below that threshold.

This should be checked again once CI/CD begins building and deploying images regularly.

---

# Cost Summary

|Resource|Tier|Lifecycle|Estimated cost|
|---|---|---|--:|
|Terraform state storage|Standing|Never normally destroyed|~$0.25/month|
|VNet / NSG / private DNS|Standing|Never normally destroyed|Negligible|
|ACR|Standing|Leave provisioned|$0 if allowance applies, otherwise ~$7/month|
|VM compute + qualifying disk|Standing|Leave running|$0 within student allowance|
|Static public IP|Standing|Leave attached|$0 under qualifying allowance|
|PostgreSQL compute + storage|Standing, time-bounded|Leave running until ~May 8, 2027|$0 until allowance expires|
|PostgreSQL private endpoint|Standing|Leave provisioned|~$10/month|
|Managed Redis|Session|Delete/recreate|$0 while absent, ~$13/month continuously|
|Redis private endpoint|Session|Delete/recreate|$0 while absent, ~$10/month continuously|

## Expected Ongoing Cost

If the ACR allowance applies, the main recurring cost is approximately:

**~$10 CAD/month**

If ACR is not covered:

**~$17 CAD/month**

Redis and its private endpoint only contribute while deliberately provisioned for testing.

Against the current **$136.90 CAD student-credit budget**, the PostgreSQL private endpoint is therefore the main standing cost to monitor.

---

# Infrastructure Lifecycle

The revised architecture now has two separate workflows:

1. a **one-time bootstrap** for standing infrastructure
    
2. a much smaller **Redis session lifecycle**
    

---

## One-Time Bootstrap

Run once during initial deployment, and again during deliberate rebuild exercises.

```text
1. Provision standing infrastructure with Terraform:
   - VNet
   - subnet
   - NSG
   - private DNS zones
   - Terraform state storage/bootstrap resources
   - ACR
   - VM
   - managed disk
   - static public IP
   - PostgreSQL
   - PostgreSQL private endpoint
   - DNS integration

2. Confirm administrative access to the VM.

3. Run the complete Ansible playbook:
   - Docker
   - Docker Compose
   - application user
   - directories and permissions
   - application configuration
   - monitoring configuration
   - nginx
   - Certbot when applicable

4. Run Alembic migrations against PostgreSQL from the VM.

5. Run the target seed script once.

6. Start the Compose application stack:
   - FastAPI
   - Prometheus
   - Grafana
   - Alertmanager
   - nginx where applicable

7. Verify:
   - /health
   - /ready
   - scheduler discovers the seeded targets
   - results persist
   - Prometheus scrapes successfully
   - Grafana is reachable
   - Alertmanager is functioning

8. Once a domain is introduced, point its DNS A record at the static public IP.
```

After this bootstrap, the standing infrastructure remains available.

A normal working session becomes:

```text
SSH into VM
    ↓
make changes
    ↓
deploy/restart affected services
    ↓
verify
```

rather than rebuilding the Azure environment from scratch.

---

# Routine Redis Session

Redis is the only major Azure component expected to cycle regularly.

## Startup

```text
1. Provision Redis and its networking resources with Terraform.
2. Confirm private DNS resolution from the VM.
3. Confirm /ready reports Redis healthy.
4. Test the Redis integration.
5. Capture the required evidence.
```

## Teardown

```text
1. Confirm application behaviour does not depend on Redis for durable state.
2. Destroy:
   - Redis private endpoint
   - DNS zone-group link
   - managed Redis
3. Verify the application returns to its expected degraded-without-Redis behaviour.
```

---

# Terraform Structure

Because only Redis now follows a routine teardown lifecycle, separating Terraform configuration into standing and session infrastructure becomes attractive.

For example:

```text
infra/
└── terraform/
    ├── standing/
    │   ├── VNet
    │   ├── VM
    │   ├── PostgreSQL
    │   ├── ACR
    │   └── persistent networking
    │
    └── session/
        ├── Redis
        └── Redis private endpoint
```

This would let:

```text
terraform destroy
```

inside the session configuration affect only Redis-related infrastructure by construction.

That is preferable to depending heavily on `-target` for routine lifecycle management.

The exact Terraform organization should still be decided while learning Terraform rather than committed to before understanding the state and dependency implications.

---

# Periodic Rebuild Drills

Keeping infrastructure standing does not remove the need to prove reproducibility.

The planned Terraform and Ansible rebuild exercises should remain.

They demonstrate that the system can be reconstructed from:

```text
Terraform
+
Ansible
+
Alembic
+
documented bootstrap steps
```

rather than merely proving that the current Azure environment has continued running successfully.

The rebuild drills should therefore be treated as deliberate exercises rather than the everyday development lifecycle.
