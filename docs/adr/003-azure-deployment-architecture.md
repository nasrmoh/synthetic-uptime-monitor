# ADR-003: Azure Deployment Architecture

## Status

Accepted. Some implementation details, particularly VM sizing and observability placement, will be refined empirically during Phase 2.

## Context

Phase 1 produced a fully containerized local deployment of the Synthetic Uptime Monitor. FastAPI, PostgreSQL, Redis, Prometheus, Grafana, and Alertmanager run as Docker Compose services on a single machine, with Compose providing internal service networking and DNS.

ADR-002 documented the decision to use containerized PostgreSQL for the local MVP and explicitly deferred the production database decision to the Azure deployment phase.

Phase 2 has a different goal. Simply recreating the Phase 1 Compose environment on an Azure VM would prove that the existing deployment can run somewhere else, but it would provide limited exposure to Azure-specific infrastructure. Instead, the architecture will keep the application and observability components containerized while moving PostgreSQL and Redis to managed Azure services.

This is primarily a learning and infrastructure-design decision rather than a response to application scale. The Synthetic Uptime Monitor is unlikely to require managed database or cache services at its expected workload. The purpose is to gain practical experience with managed-service networking, authentication, configuration, lifecycle, and operational tradeoffs while still preserving the application architecture built during Phase 1.

The deployment is also constrained by the Azure for Students credit. Resource selection and lifecycle therefore need to account for cost as well as architecture.

## Decision

### Compute

The application will initially run on a single Azure Linux VM.

The VM will host:

- the FastAPI application container
    
- Prometheus
    
- Grafana
    
- Alertmanager
    
- nginx
    
- supporting Docker Compose configuration
    

PostgreSQL and Redis will run outside the VM as managed Azure services.

The initial target is a small VM size, likely a B-series instance. The exact size is intentionally not fixed by this ADR because the actual resource requirements of the application and observability stack have not yet been measured in Azure.

Two questions remain open and will be resolved empirically:

1. **Can the selected low-cost VM run the application and full observability stack simultaneously?**
    
    This will be tested after the first deployment. If the VM cannot support the complete stack reliably, the architecture will be reconsidered based on measured CPU and memory usage rather than assumptions.
    
2. **Should some observability workloads run elsewhere?**
    
    Possible alternatives include a second Azure VM or the existing y540-server. These are not current decisions. They will only be considered if measurements show that the primary VM does not have sufficient headroom.
    

A second Azure VM would also increase VM-hour consumption, so splitting the deployment is both an architectural and cost decision.

### PostgreSQL

Use **Azure Database for PostgreSQL Flexible Server**.

This replaces the temporary Phase 1 decision documented in ADR-002.

The Phase 1 deployment already provided experience operating PostgreSQL as a container, including volumes, migrations, Compose networking, readiness checks, and failure behaviour. Repeating the same configuration on an Azure VM would add relatively little new learning.

Using the managed PostgreSQL service instead introduces a different operational model:

- connecting to an external managed database
    
- configuring Azure networking and access rules
    
- using encrypted database connections
    
- managing deployment-provided connection information
    
- separating application infrastructure from database infrastructure
    
- operating a database whose underlying host is not administered directly
    

PostgreSQL will be stopped between development sessions where practical and kept running continuously only when the deployed project needs to remain available.

### Redis

Use a managed Azure Redis service.

Redis differs from PostgreSQL in an important way for this project: Redis stores disposable operational state rather than authoritative data. PostgreSQL remains the system of record.

Because Redis cannot be treated as persistent application storage, deleting and recreating it does not violate the application's data model. The application should already tolerate Redis state disappearing and being rebuilt.

The intended development workflow is therefore:

1. provision Redis when managed Redis integration needs to be tested;
    
2. verify the application works against it;
    
3. capture the required evidence;
    
4. remove it when continuous availability is unnecessary;
    
5. provision it continuously only when the complete Azure deployment needs to remain online.
    

This limits unnecessary spending while still providing experience operating the application against a managed Redis service.

### Observability

Keep the existing:

- Prometheus
    
- Grafana
    
- Alertmanager
    

The project will not replace these with Azure-native observability during Phase 2.

Phase 1 already produced working metrics, dashboards, alert rules, and an end-to-end failure path from a failed check through Prometheus and Alertmanager. Replacing the stack would discard useful existing work without solving a problem currently present in the project.

Keeping it also preserves continuity between the local and Azure versions of the system. The same observability components used to understand the local application can now be used to understand the cloud deployment.

The final physical location of the observability services remains open pending VM resource measurements.

### Configuration Management

Use **Ansible** to configure the Linux VM.

Terraform and Ansible will have deliberately separate responsibilities.

Terraform will define the Azure infrastructure that must exist.

Ansible will configure the operating system and software environment of the VM after that infrastructure exists.

Its responsibilities are expected to include:

- Docker installation and configuration
    
- Docker Compose
    
- nginx
    
- Certbot
    
- application directories
    
- users and permissions
    
- deployment configuration files
    
- observability configuration
    

Ansible will not configure the operating systems underlying PostgreSQL or Redis because those are managed services.

Starting and stopping Azure resources between development sessions is also outside Ansible's responsibility. That is an operational lifecycle task and can be handled through the Azure CLI or small manually written scripts.

For the VM specifically, cost-control procedures must ensure it is **deallocated** through Azure when it is not required rather than merely shut down from inside the guest operating system.

### Networking

The detailed networking design (NSG rules, subnet layout) will be completed before Terraform implementation. The intended high-level boundary is:

- nginx is the only public HTTP/HTTPS entry point (once Part 3 is reached, nothing is public before then)
- FastAPI is not directly exposed to the public internet; nginx proxies to it internally
- PostgreSQL is reachable only privately, within the VNet, via private endpoint, never a public endpoint
- Redis is reachable only privately, within the VNet, via private endpoint, with public network access explicitly disabled, never a public endpoint
- Prometheus and Alertmanager are not public services
- Grafana access will be explicitly decided rather than exposed by default
- SSH access is administrative only, over Tailscale, not open to the public internet
- The personal laptop's only network relationship to this infrastructure is with the VM itself. Any access to Postgres, Redis, or the observability stack happens through the VM acting on the laptop's behalf (e.g. an SSH tunnel), never by the laptop connecting to those services directly

This treats the personal laptop as a guest of the VM, not a trusted peer of the wider Azure network: it can reach the VM, and the VM can reach everything else, but the laptop never gets a direct line to anything beyond the VM.
### Cost

Cost is an architectural constraint rather than an afterthought.

Current expectations are:

- **Linux VM:** deallocated between development sessions when possible
    
- **PostgreSQL:** stopped between sessions where practical and kept continuously available only when required
    
- **Redis:** created only when required during development if continuous billing makes idle operation wasteful
    
- **Observability:** runs wherever the selected compute architecture can support it without unnecessarily adding another paid resource
    

The Azure for Students credit is the project's primary cloud budget.

Exact resource pricing and budget alerts will be handled separately during the Phase 2 cost-guardrail work.

## Alternatives Considered

### Azure Container Apps

Azure Container Apps was considered as the primary compute platform.

It was rejected because it would remove several of the infrastructure responsibilities that Phase 2 is specifically intended to explore.

The planned VM architecture provides concrete roles for:

- Terraform
    
- Linux administration
    
- Ansible
    
- Docker
    
- nginx
    
- Certbot
    
- NSG configuration
    
- operating-system troubleshooting
    

Container Apps would be a reasonable choice if the goal were simply to deploy the application with less infrastructure management. That is not the primary objective of this phase.

### Containerized PostgreSQL and Redis on the VM

Running PostgreSQL and Redis as Compose services on the Azure VM would closely reproduce the Phase 1 architecture.

This was rejected as the default because that deployment model has already been implemented and tested locally.

Using managed services introduces new infrastructure concerns rather than repeating the same ones:

- external service networking
    
- managed-service authentication
    
- lifecycle management
    
- cloud configuration
    
- separation between compute and persistence
    

A fully containerized VM deployment remains a fallback if cost or Azure service limitations make the managed architecture impractical.

### Azure-Native Observability

Replacing Prometheus, Grafana, and Alertmanager with Azure-native monitoring was considered.

It was rejected for Phase 2 because the existing observability stack is already functional and represents a significant part of the Phase 1 project.

The goal is to deploy and operate that system in Azure, not replace functioning components solely because Azure alternatives exist.

### Two-VM Deployment

Splitting application and observability workloads across separate Azure VMs is not currently selected.

It remains a possible response if measurements show that a single low-cost VM cannot reliably run the required containers.

The decision will be based on measured resource usage and cost rather than assumed ahead of deployment.

## Consequences

### Benefits

This architecture provides:

- practical experience provisioning and administering an Azure Linux VM
    
- a clear distinction between Terraform and Ansible responsibilities
    
- exposure to managed PostgreSQL and Redis
    
- continued use of the Phase 1 observability work
    
- an explicit public/private network boundary
    
- experience operating a system whose application, persistence, and cache are no longer located on one Docker network
    
- a deployment architecture that can later support CI/CD, nginx, TLS, and the Phase 3 benchmark work
    

### Costs and Responsibilities

This architecture also introduces:

- more networking configuration than a single-VM Compose deployment
    
- managed-service configuration and authentication
    
- additional Azure resources that must be monitored for cost
    
- dependence on Azure service availability during cloud testing
    
- uncertainty around the resource requirements of the observability stack
    
- additional failure boundaries between the application, database, and cache
    

The architecture therefore requires deliberate cost management and stronger configuration discipline than Phase 1.

## Open Items

The following decisions are intentionally deferred until evidence exists:

- exact Linux VM size
    
- whether one VM has enough capacity for the application and observability stack
    
- whether observability should eventually move to another VM or the y540-server
    
- exact NSG rules and networking port table
    
- Grafana's final access model
    
- the exact lifecycle workflow used to start, stop, create, or destroy development resources
    

These items should be resolved through testing during Phase 2 rather than guessed at in this ADR.

## Summary

The initial Azure architecture will use:

```text
Internet
   |
   v
Azure Linux VM
   |
   +-- nginx
   |
   +-- FastAPI
   |
   +-- Prometheus
   |
   +-- Grafana
   |
   +-- Alertmanager
   |
   +------> Azure Database for PostgreSQL Flexible Server
   |
   +------> Managed Azure Redis
```

Terraform will create the Azure infrastructure.

Ansible will configure the Linux VM.

nginx will provide the public application entry point.

PostgreSQL will remain the durable source of truth.

Redis will remain disposable operational state.

Prometheus, Grafana, and Alertmanager will continue to provide the project's observability layer.

The architecture deliberately leaves VM sizing and observability placement open until measurements from the real deployment justify a decision.