# Architecture Note: Split Deployment — Azure VM + y540-server

## Summary

The deployment is now split across two hosts connected through Tailscale, with each host running its own Docker Compose stack.

```text
Azure VM (synth-vm)              y540-server
──────────────────               ─────────────────────────
FastAPI app                      Prometheus
scheduler/checker                Grafana
nginx (pending)                  Alertmanager
        │                              ▲
        └──── /metrics over Tailscale ─┘
        │
        ├──── Azure PostgreSQL Flexible Server
        └──── Azure Managed Redis
```

The Azure VM is responsible for the application itself.

The y540-server is responsible for observability.

The two hosts do not share a Docker network. The only cross-host connection required is Prometheus on y540 scraping the Azure VM's `/metrics` endpoint over the private Tailscale network.

The Azure VM can be reached through its Tailscale IP for application endpoints such as:

```text
/health
/ready
/docs
/metrics
```

The y540-server can be reached through its own Tailscale IP for:

```text
Grafana      :3000
Prometheus   :9090
Alertmanager :9093
```

---

## Why We Split the Deployment

Originally, the Azure VM ran the entire Compose stack:

```text
FastAPI
Prometheus
Grafana
Alertmanager
```

This worked, but the VM became noticeably less responsive when the full stack was running. The slowdown became more apparent when the application was actively checking targets.

Grafana was the largest individual container in the measurements we took

We considered two other options:
- using a second Azure VM for observability
- moving toward Kubernetes / multiple application replicas

A second Azure VM would increase infrastructure complexity and consume more of the available VM allowance.

Kubernetes would introduce a much larger architectural change and solve scaling problems the application does not currently have.

The existing y540-server already has sufficient resources and is already connected to the Azure VM through Tailscale, making it the simplest solution.

This decision is recorded in ADR-005.

---

## Deployment Configuration Flow

Terraform and Ansible continue to have separate responsibilities.

```text
Terraform
    ↓
creates Azure infrastructure
    ↓
determines deployment-specific values
    ↓
renders local deployment files from templates
    ↓
Ansible
    ↓
configures both hosts
    ↓
copies the correct deployment files to each host
```

Terraform handles values that are only known after infrastructure creation, such as:

- PostgreSQL hostname
- Redis hostname
- Redis access key
- VM Tailscale/public address
- environment-specific deployment values

Secrets that we choose manually, such as PostgreSQL and Grafana credentials, are supplied through a local `.tfvars` file that is not committed to Git.
## Terraform Templates

Terraform templates live under:

```text
infra/terraform/templates/
```

The current templates include:

|Template|Purpose|Destination|
|---|---|---|
|`vm-deployment-env.tftpl`|Application environment variables, including PostgreSQL and Redis connection details|Azure VM|
|`linux-server-deployment-env.tftpl`|Environment variables required by Grafana and the observability stack|y540-server|
|`linux-server-prometheus.tftpl`|Prometheus configuration with the Azure VM's scrape address inserted|y540-server|
|`inventory.tftpl`|Ansible inventory containing the host connection details for both machines|Ansible controller|

Terraform renders these using `templatefile()` and `local_file`.

The resulting generated files are written into the project's local deployment directory.

For example:

```text
deploy/
├── vm-deployment-env
├── linux-server-deployment-env
├── linux-server-prometheus.yaml
├── azure-vm-compose.yml
└── linux-server-observe-compose.yml
```

The generated names are deliberately host-specific locally so it is clear which machine each file belongs to.

---

## Ansible's Role

Ansible does not need to calculate deployment values itself.

Its job is to configure each machine and copy the appropriate generated files into place.

### Azure VM

Ansible places:

```text
vm-deployment-env
    ↓
/opt/synthetic-uptime-monitor/.env

azure-vm-compose.yml
    ↓
/opt/synthetic-uptime-monitor/docker-compose.yml
```

The resulting directory is roughly:

```text
/opt/synthetic-uptime-monitor/
├── .env
└── docker-compose.yml
```

The Azure Compose stack contains the FastAPI application and scheduler/checker.

---

### y540-server

Ansible places:

```text
linux-server-deployment-env
    ↓
/opt/synthetic-uptime-monitor/.env

linux-server-observe-compose.yml
    ↓
/opt/synthetic-uptime-monitor/docker-compose.yml

linux-server-prometheus.yaml
    ↓
/opt/synthetic-uptime-monitor/prometheus.yml
```

It also copies the existing monitoring configuration.

The resulting directory is roughly:

```text
/opt/synthetic-uptime-monitor/
├── .env
├── docker-compose.yml
├── prometheus.yml
└── monitoring/
```

The y540 Compose stack contains:

```text
Prometheus
Grafana
Alertmanager
```

---

## Prometheus Cross-Host Scraping

Previously, Prometheus and FastAPI were part of the same Compose stack.

This meant Prometheus could scrape:

```text
app:8000
```

because `app` was resolved through Docker Compose's internal DNS.

After splitting the deployment, the containers no longer share a Docker network.

Prometheus therefore needs to reach the Azure VM as a normal remote host.

Terraform renders the Azure VM address into the Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'synthetic-uptime-monitor'
    static_configs:
      - targets: ['<vm-tailscale-ip>:8000']
```

The resulting path is:

```text
Prometheus container
        ↓
y540 host
        ↓
Tailscale
        ↓
Azure VM :8000
        ↓
FastAPI /metrics
```

This has been verified successfully.

Prometheus can scrape the Azure VM, while Grafana and Alertmanager continue to communicate with Prometheus through Docker Compose networking on y540.

---

## Current Environment Separation

The Azure VM receives application-specific values such as:

```text
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
DATABASE_URL
REDIS_URL
SCHEDULER_ENABLED
```

The y540-server receives observability-specific values such as:

```text
GF_SECURITY_ADMIN_USER
GF_SECURITY_ADMIN_PASSWORD
PROMETHEUS_URL
```

Each machine therefore receives only the configuration required for its role.

---

## Why This Shape Works Well

### Clear host responsibilities

```text
Azure VM
→ application execution

y540-server
→ observability
```

Each host has a narrow purpose.

### No second Azure VM

We avoid consuming additional Azure VM capacity simply to run monitoring components.

### Private monitoring path

Prometheus reaches the application through Tailscale rather than exposing the application's metrics port publicly.

### Terraform owns deployment-specific values

Values that are only known after infrastructure creation can be inserted into generated files automatically.

### Ansible remains simple

Ansible configures the hosts and copies the rendered files into place instead of maintaining a second source of configuration logic.

### Standard filenames on deployed hosts

Both hosts see conventional files:

```text
.env
docker-compose.yml
prometheus.yml
```

The host-specific naming only exists in the local deployment directory.

This keeps direct SSH debugging simple because each machine looks like a normal standalone Compose deployment.