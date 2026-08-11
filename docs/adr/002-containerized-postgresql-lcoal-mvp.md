# ADR-002: Containerized PostgreSQL (Local MVP) vs Managed Azure PostgreSQL

## Status
Accepted

## Context

As of Phase 1's completion, PostgreSQL runs as a container inside our Docker Compose stack, on our local machine, or on the y540-server. Compose handles DNS resolution between services. Postgres is our persistence layer for endpoint targets and check-result history.

This was the easier path for Phase 1: no Azure setup, no cost, and we only had to take care of the machines the containers run on. It also gave us a local preview of problems we'd otherwise hit blind in the cloud. The clearest example: we hit DNS resolution issues early on, caused by conflating local `localhost` with the Compose network's service-name resolution. Having debugged that locally means that if a similar connection issue shows up in Azure, we already have a diagnostic question ready: "is this a DNS issue?"

The app connects via `DATABASE_URL`, so the database's location is not hardcoded. Moving it later does not require an application redesign.

We do not expect to hit a resource ceiling on persistence for a synthetic uptime monitor at our scale, so this decision is being evaluated on cost, control, and operational overhead, not performance.

## Decision

Use containerized PostgreSQL within Docker Compose for local development and the Phase 1 MVP. This is explicitly not a production decision. The production database architecture is deferred to the Azure architecture ADR.

## Alternatives Considered

**Current setup: containerized Postgres, on-prem (local machine / y540-server)**

This is effectively an on-prem setup. Cost is close to just electricity and network, genuinely cheap on a per-month basis. But control comes with a real cost we pay elsewhere: everything is set up and maintained by us directly, and the y540-server itself represents a real capital cost (~$1000 to fix up and dedicate as a server). If we needed more resource headroom, the only path is buying more hardware. High control, but the ops overhead and upfront hardware cost are both ours to carry. The upside is flexibility: moving the server, changing its OS, or reconfiguring it is entirely in our hands.

**Option A: Azure VM running the full Compose stack (or Postgres specifically)**

This wouldn't necessarily be Postgres on its own dedicated instance. Realistically the whole Compose stack could live on one VM, similar to what we have now but hosted. The advantage over on-prem shows up at scale: if resource or availability became a concern, provisioning and managing multiple Azure-managed VMs is much easier than configuring multiple physical machines by hand. We could also split specific containers onto separate VMs if needed, though that's likely unnecessary at our scale. This still means we manage Postgres ourselves, just on Azure's hardware instead of ours, so ops overhead for the database itself doesn't really drop.

**Option B: Azure Database for PostgreSQL (managed, PaaS)**

We still own schema design and migrations, but Azure takes over OS patching, software updates, and infrastructure concerns, and likely gives us a straightforward path to scale if demand grows. Cost shifts from CapEx (buying/fixing a server) to OpEx (a recurring cloud bill), and the frontend cost is lower since there's no hardware to buy. The tradeoff is less control in exchange for less operational burden, which seems like the right trade if the ops overhead is the thing we're actually trying to reduce.

## Consequences

**Advantages of the current (containerized, local) approach**
- Easy to set up, start, and stop
- Zero cloud cost during Phase 1
- Gave us early, inexpensive exposure to problems (DNS resolution, volumes, migrations, failure behavior) that will recur in Azure, at a point where debugging them was low-stakes

**Disadvantages**
- We are responsible for the machine it runs on, including its upfront hardware cost
- No managed backup, patching, or HA story
- Local reliability doesn't prove anything about production database behavior

## Future Implication

This decision must be revisited before Azure deployment. The two live options at that point are an Azure VM running Postgres ourselves (Option A) or Azure Database for PostgreSQL Flexible Server (Option B). That decision should weigh cost (CapEx vs OpEx), backup and recovery story, operational burden, networking, and how much control we actually want to give up. 