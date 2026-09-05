# ADR-005: Move Observability to Linux Server

## Status

Accepted.

## Context

The full deployment currently runs the application alongside Prometheus, Grafana, and Alertmanager on the Azure VM.

Testing showed that running the full Compose stack reduced the VM's responsiveness. The slowdown became more noticeable once the application began actively checking targets.

A second Azure VM was considered for the observability stack, but this would effectively split the available VM-hour allowance across two machines.

## Decision

Move the observability services to the existing Linux server:

- Prometheus
    
- Grafana
    
- Alertmanager
    

The Azure VM will continue to run the main application.

The Linux server is already connected to the Azure VM through Tailscale, so Prometheus can scrape the application's `/metrics` endpoint over the private Tailscale network.

## Resulting Architecture

```text
Azure VM
  ├── FastAPI
  ├── Scheduler / Checker
  └── nginx
        |
        | /metrics over Tailscale
        v
Linux Server
  ├── Prometheus
  ├── Grafana
  └── Alertmanager
```

## Consequences

- The Azure VM has fewer services competing for its limited resources.
    
- No second Azure VM is required.
    
- Observability now depends on the Linux server and Tailscale being available.
    
- Prometheus, Grafana, and Alertmanager are no longer part of the Azure VM's Compose stack.