# ADR-004: PostgreSQL VNet Integration

## Status

Accepted. This ADR amends the PostgreSQL networking decision in ADR-003. All other decisions in ADR-003 remain unchanged.

## Context

ADR-003 originally chose a private endpoint for Azure Database for PostgreSQL Flexible Server.

Further cost analysis changed PostgreSQL from session infrastructure to standing infrastructure. Because the PostgreSQL server is expected to remain provisioned continuously, the recurring cost of a private endpoint would also become a standing cost.

Further research showed that PostgreSQL Flexible Server can instead use private access through VNet integration. This provides private communication between the application VM and PostgreSQL without requiring a PostgreSQL private endpoint.

## Decision

Use **VNet integration with private access** for PostgreSQL Flexible Server instead of a private endpoint.

PostgreSQL will use its own delegated subnet that contains no other resource types.

The planned network layout is:

```text
VNet
172.16.1.0/16

├── app-subnet
│   └── Linux VM
│
├── postgres-subnet
│   └── PostgreSQL Flexible Server
│
└── private-endpoints-subnet
    └── Redis private endpoint
```

The application VM and PostgreSQL server will communicate privately through the VNet.

The exact PostgreSQL subnet size and private DNS configuration will be confirmed against the Azure documentation before the database is provisioned.

## Alternatives Considered

### PostgreSQL Private Endpoint

The original design used a private endpoint.

Private endpoints provide more flexibility when a service must be privately reachable from multiple VNets, peered networks, or more complicated hybrid environments.

This project currently has one application VM and one PostgreSQL server inside a single Azure VNet. That additional flexibility does not justify a continuously billed private endpoint for the current architecture.

## Consequences

* PostgreSQL's networking mode is chosen when the server is created. Changing to a different networking model later may require recreating the server.
* PostgreSQL requires its own delegated subnet and that subnet cannot be used for unrelated resources.
* The database becomes part of the VNet dependency structure, so the VNet and PostgreSQL lifecycle must be handled accordingly by Terraform.
* Redis will continue to use a private endpoint and will remain session infrastructure, so the project still gains experience with both VNet integration and Azure Private Link.
* The continuously billed PostgreSQL private endpoint is removed from the standing cost model.

## Not Changed

All other compute, Redis, observability, configuration-management, and networking decisions from ADR-003 remain unchanged.
