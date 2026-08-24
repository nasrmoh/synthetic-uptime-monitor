# Azure Networking Mental Model

The easiest way to understand Azure networking is to start from what we already know from Docker Compose. The same ideas exist in both environments, only with more layers and more explicit policy in Azure.

The shape of every connection we care about is the same in either place:

```text
application
    ↓
hostname
    ↓
DNS resolves the hostname to an IP address
    ↓
traffic is sent to that host on a specific port
    ↓
the service listening on that port receives it
```

---

## 1. Host, port, service, and listening

A useful analogy is an office building.

```text
IP address = the street address of the building
port       = the desk number inside it
service    = the team working at that desk
listening  = that desk is staffed and accepting visitors
```

So `172.16.1.4:5432` means: go to this machine, and deliver the connection to port 5432.

One machine runs many services at once, each on its own port:

```text
Machine: 172.16.1.4
  22   → SSH
  80   → HTTP
  443  → HTTPS
  5432 → PostgreSQL
  6379 → Redis
```

### What listening actually means

A service asks the operating system to listen on a port. PostgreSQL listening on 5432 is PostgreSQL telling the OS: if traffic arrives for port 5432, hand it to me.

```text
traffic arrives at the machine
    ↓
destination port = 5432
    ↓
OS checks which process is listening on 5432
    ↓
PostgreSQL
```

### Two failures that look similar and are not

We will use this distinction deliberately during the SSH failure drill.

|Situation|What the client sees|
|---|---|
|Nothing is listening on the port, but the packet reached the machine|The OS refuses immediately. Connection refused.|
|A firewall dropped the packet before it reached the machine|Nothing answers at all. The connection hangs, then times out.|

An immediate refusal means we reached the building and found an empty desk. A hang means we never got through the front door.

---

## 2. What Docker Compose was doing

Our local stack already used most of these ideas.

```text
postgresql://user:password@db:5432/database
```

The part that matters is `db:5432`. `db` is a hostname and 5432 is a port.

Compose creates a private network for the project (a Linux bridge) and gives each container an address on it:

```text
Compose network
├── app container    private IP, for example 172.18.0.2
├── db container     private IP, for example 172.18.0.3
└── redis container  private IP, for example 172.18.0.4
```

Compose also runs a DNS resolver inside that network. Each container's `/etc/resolv.conf` points at `127.0.0.11`, an embedded resolver Docker runs in the container's network namespace. When our app asked for `db`, that resolver answered with the db container's private IP.

So the pieces were already there: a private address space, private addresses, and a directory turning names into addresses.

---

## 3. Moving the idea to Azure

Azure does the same things with more explicit separation.

|Docker Compose|Azure|Question it answers|
|---|---|---|
|Compose network|VNet|What private network exists between our resources?|
|no equivalent|Subnet|Which portion of that network does this resource join?|
|container private IP|Private IP|How is this resource addressed privately?|
|Docker's embedded resolver|Azure DNS / Private DNS Zone|How do names become IP addresses?|
|published port (`-p 8000:8000`)|Public IP|How can something outside reach it?|
|no equivalent|NSG|Which traffic is permitted?|

Two rows have no Compose equivalent, and those are the two that feel unfamiliar. Compose gives us one flat network where everything is neighbours with everything, and no firewall at all. Azure lets us divide the space and control traffic across it, which is the entire reason "private" can mean anything.

---

## 4. VNet

A virtual network defines a private address space in Azure. For this project:

```text
172.16.0.0/16
```

Using the neighbourhood analogy, the VNet is the neighbourhood. It does not describe one machine. It describes the private space our resources can address each other within.

### Reading `172.16.0.0/16`

The notation describes a _range_, not a single address.

- `172.16.0.0` is the network address, the start of the range
- `/16` says how many leading bits are fixed as the network portion

An IPv4 address is 32 bits:

```text
172      .16       .0        .0
10101100 .00010000 .00000000 .00000000
```

With `/16`, the first 16 bits are fixed and the remaining 16 are free for addresses:

```text
 network portion  |  available for addresses
 172      .16     |  .x        .x
 <---- 16 bits --->  <---- 16 bits ---->
```

So this VNet covers `172.16.0.0` through `172.16.255.255`, which is 2^16 = **65,536 addresses**.

`/16` is the CIDR prefix length. A larger prefix number means more fixed network bits and therefore a smaller range.

|CIDR|Address pattern|Total addresses|Usable in Azure|
|---|---|--:|--:|
|`/16`|`172.16.x.x`|65,536|65,531|
|`/24`|`172.16.1.x`|256|251|
|`/28`|part of `172.16.1.x`|16|11|
|`/32`|one exact address|1|n/a, used for rules not subnets|

Azure reserves five addresses in every subnet: the network address, three for the gateway and internal DNS, and the broadcast address. That is why usable is always total minus five, and it is why very small subnets run out faster than the arithmetic suggests.

We chose `172.16.0.0/16` rather than `10.0.0.0/16` deliberately. All three of `10.0.0.0/8`, `172.16.0.0/12`, and `192.168.0.0/16` are private ranges reserved by RFC 1918, so any of them is valid. `10.0.0.0/16` is the near-universal default, which makes it the range most likely to collide if this VNet ever needs to peer with another network or reach a home network over a VPN.

---

## 5. Subnets

A subnet is a smaller slice of the VNet's address space.

```text
VNet = neighbourhood
Subnet = a street within it
```

Our layout:

```text
VNet: 172.16.0.0/16

├── app-subnet          172.16.1.0/24
│     └── Linux VM
│
├── postgres-subnet     172.16.2.0/24    delegated to the PostgreSQL service
│     └── PostgreSQL Flexible Server, injected
│
└── redis-pe-subnet     172.16.3.0/24
      └── Redis private endpoint
```

Three subnets rather than two, because PostgreSQL and Redis use **different private networking models**. Section 9 covers why. The short version is that PostgreSQL sits _in_ a subnet we delegate to it, and that subnet can hold nothing else, so it cannot share space with the Redis endpoint.

`/24` blocks give 251 usable addresses each, far more than any of these need. That is intentional. Carving out a spare `/24` costs nothing when the VNet holds 65,536 addresses, while resizing a subnet that already has resources attached forces those resources to be replaced.

## 6. Private IP

A private IP identifies a network interface inside the private network. Our VM might hold `172.16.1.4`.

```text
VNet       = neighbourhood
Subnet     = street
Private IP = building address
```

Any resource that can route through the VNet can reach the VM at that address. Nothing on the public internet can, because these ranges are not internet-routable.

---

## 7. Public IP

A public IP is an internet-routable address. It gives something outside the VNet a way to address a resource.

Our eventual shape:

```text
Internet
    ↓
Public IP
    ↓
NSG decides whether the traffic is permitted
    ↓
VM, nginx on 443
    ↓
FastAPI
```

The NSG sits in that path deliberately. A public IP makes a resource _addressable_ from the internet. It does not make it _reachable_. Reachability is the NSG's decision.

Only the VM gets a public IP. Everything else stays private:

```text
VM / nginx  → public entry point
PostgreSQL  → private
Redis       → private
Prometheus  → private
Alertmanager→ private
FastAPI 8000→ private
```

---

## 8. DNS

Addresses are convenient for machines and inconvenient for everything else. DNS lets us use names.

The reason this matters operationally, rather than just for readability, is stability. A private endpoint may be assigned a different private IP when it is destroyed and recreated, and Redis is on exactly that destroy-and-recreate cycle. A name can stay constant across that. This is why our configuration references private DNS hostnames rather than private IPs.

Azure's mechanism here is the **Private DNS Zone**: a zone we own, linked to our VNet, which answers queries for a specific domain differently inside the VNet than the public internet would. Both of the models in the next section depend on it, which is why the cost model treats private DNS zones as standing infrastructure with their own lifecycle rather than as part of the thing they point at.

---

## 9. Two private networking models

### PostgreSQL: VNet integration (injection)

The server is placed **inside** our VNet, in a subnet we delegate to the PostgreSQL service. It holds a private IP from our own address range. Delegation is us telling Azure that this subnet is reserved for that service to manage, and that nothing else may live there.

```text
FastAPI on the VM
    ↓  <<server-name>>.private.postgres.database.azure.com:5432
Private DNS Zone
    ↓  the server's private IP, 172.16.2.x, inside our subnet
PostgreSQL Flexible Server
```

The house is on our street. Under the neighbourhood analogy this needs no correction: the database really is in the VNet, addressed the same way the VM is.

### Redis: private endpoint (Private Link)

The service runs in Microsoft's infrastructure. What lives in our subnet is a **network interface representing it**, holding a private IP from our range, forwarding traffic to the managed service over Private Link.

```text
FastAPI on the VM
    ↓  <<cache-name>>.redis.cache.windows.net:6380
Private DNS Zone
    ↓  the private endpoint's private IP, 172.16.3.x
Azure Private Link
    ↓
managed Redis
```

Here the analogy does need the correction: the house is not on our street. There is a door on our street that leads to the house.

### Comparing them

| |VNet integration|Private endpoint|
|---|---|---|
|Where the service lives|inside our VNet|Microsoft's network|
|What occupies our subnet|the server itself|a NIC representing it|
|Subnet requirement|delegated, exclusive to the service|ordinary subnet, shares fine|
|Cost|no extra networking charge|hourly charge per endpoint, plus data processing|
|Coupling|tied to that subnet for its lifetime|service is not embedded in our address space|
|When DNS resolves but nothing connects|unlikely, routing and DNS are coupled|possible, routing and DNS are separate concerns|

### Why we chose each

**PostgreSQL uses VNet integration** because it is standing infrastructure. It runs continuously for months, so a per-hour endpoint charge accumulates, and that charge was the largest standing cost in our model. We gain nothing from the flexibility a private endpoint buys, since we have one VNet, no peering, and no on-premises network.

**Redis uses a private endpoint** because it is session infrastructure on a create, prove, destroy cycle. The hourly charge only applies while it exists, which makes it the cheapest possible place to learn this model. We end up with hands-on experience of both patterns while paying a standing charge for neither.

### The sharp edge

The two modes are **mutually exclusive and chosen when the server is created.** A Flexible Server created with VNet integration cannot later have a private endpoint added, and the private endpoint path requires creating the server in public access mode and then firewalling the public endpoint closed. So "private endpoint" does not mean no public endpoint exists; it means one exists and we shut it.

This is why the networking mode is decided before the VNet is applied rather than during the PostgreSQL work. Changing our mind later means recreating the database.

## 10. NSG

A Network Security Group controls which traffic Azure permits.

```text
The VNet answers:  where does this resource live?
The NSG answers:   which traffic may reach it, or leave it?
```

An NSG is an ordered list of rules, each specifying:

- direction, inbound or outbound
- source and destination
- port and protocol
- allow or deny
- a priority number that determines evaluation order

Examples we will actually write:

```text
allow  443 inbound  from Internet
allow  22  inbound  from <<our public IP>>   temporary, removed once Tailscale works
deny   8000 inbound from Internet            FastAPI is never public
```

Three things worth holding onto:

**Every NSG comes with default rules.** These permit traffic within the VNet, permit outbound to the internet, and deny inbound from the internet. That is why resources are private by default and why we mostly write rules to _open_ things rather than to close them.

**An NSG is not the VM's own firewall.** The NSG operates in Azure's network, before traffic reaches the machine. The VM can also run its own firewall inside the guest OS. Both can block the same port for different reasons, which is worth remembering the first time something is unreachable and the NSG looks correct.

**NSG behaviour on the two special subnets is not the same as on ordinary ones.** A delegated subnet and a private endpoint subnet each carry their own constraints on what NSG rules do there. Worth checking before assuming a rule we wrote is being enforced the way we expect.

---

## 11. Where an NSG attaches

An NSG can be associated with a **subnet** or with a **network interface (NIC)**, and both can be in effect simultaneously.

A VM reaches the network through a NIC:

```text
VM
 ↓
NIC
 ↓
Subnet
 ↓
VNet
```

### Subnet-level

```text
app-subnet
├── VM A
├── VM B
└── VM C
```

Rules apply to everything in the subnet. A fourth VM added later inherits the policy without anyone remembering to configure it. That is the strength: policy follows the location.

### NIC-level

Rules apply to one interface. Policy follows the machine, including if it moves to a different subnet. More specific, and easier to get inconsistent across a fleet.

### When both exist

Traffic must be permitted by both. Either one denying is enough to block it, so this is an intersection rather than a union.

The evaluation order differs by direction:

```text
inbound:   subnet NSG  →  NIC NSG  →  VM
outbound:  NIC NSG     →  subnet NSG  →  out
```

In both cases the NSG closer to the network edge is evaluated first relative to where the traffic is heading. Worth verifying this against Microsoft's documentation rather than trusting a note, since it is the sort of detail that decides where we look first when something is blocked.

---

## 12. Complete picture

```text
                         Internet
                            │
                            │ public IP
                            ▼
                         [ NSG ]
                            │
                    Azure Linux VM
                    private IP 172.16.1.x
                            │
                     app-subnet
                    172.16.1.0/24
                            │
                    ┌───────┴────────┐
                    │      VNet      │
                    │  172.16.0.0/16 │
                    └───┬────────┬───┘
                        │        │
          postgres-subnet        redis-pe-subnet
          172.16.2.0/24          172.16.3.0/24
          delegated                      │
                │                        │
                ▼                        ▼
      PostgreSQL Flexible        Redis private
      Server, injected           endpoint (NIC)
      172.16.2.x                 172.16.3.x
                                         │
                                         ▼
                                Azure Private Link
                                         │
                                         ▼
                                  managed Redis
```

The asymmetry in that diagram is the point. PostgreSQL terminates inside the VNet. Redis has one more hop, because what sits in our subnet is a representative rather than the service itself.

DNS runs alongside all of this rather than inside it:

```text
application asks for a service hostname
    ↓
Private DNS Zone linked to our VNet resolves it
    ↓
a private IP in one of our subnets
    ↓
connection opens to the service port
```
## 13. What each primitive answers

|Primitive|What it answers|
|---|---|
|**VNet**|What private address space exists for our resources.|
|**Subnet**|Which slice of that space a resource joins, and therefore which policy applies to it.|
|**Subnet delegation**|Which Azure service has exclusive use of a subnet, so it can place its own resources there.|
|**Private IP**|How to address a network interface from inside the network.|
|**Public IP**|How something outside the network can address a resource. Addressable is not the same as reachable.|
|**Private endpoint**|How a service living outside our VNet becomes addressable from inside it.|
|**Private DNS Zone**|How a hostname resolves to a private address for anything inside our VNet.|
|**NSG**|Which traffic Azure permits in or out, evaluated before it reaches the machine.|
|**Port**|Which service on a host receives the connection. The IP finds the host; the port finds the service.|
