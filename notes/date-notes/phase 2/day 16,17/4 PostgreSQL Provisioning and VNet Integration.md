# Provisioning PostgreSQL

We will be using **Azure Database for PostgreSQL Flexible Server** as our managed PostgreSQL service.

For networking, we are using **VNet integration** instead of creating a separate private endpoint. This lets the PostgreSQL server communicate privately inside our VNet while avoiding the additional cost of another private endpoint.

To do this, PostgreSQL needs its own dedicated subnet. In our `main.tf`, the PostgreSQL subnet uses:

```text
172.16.2.0/24
```

This subnet is delegated to PostgreSQL Flexible Server, meaning Azure reserves it for PostgreSQL resources.

For the PostgreSQL deployment, we need three main resources:

1. A private DNS zone
    
2. A private DNS zone VNet link
    
3. The PostgreSQL Flexible Server
    

## Private DNS Zone

We create a private DNS zone using:

```text
synth.postgres.database.azure.com
```

The DNS zone acts as a private DNS namespace where PostgreSQL-related DNS records can exist.

On its own, however, this zone is not automatically visible to our VNet.

## Private DNS VNet Link

The `azurerm_private_dns_zone_virtual_network_link` resource connects our private DNS zone to the VNet.

Without this link, resources inside the VNet, such as our VM, would not be able to resolve hostnames stored inside the private DNS zone.

Conceptually:

```text
Private DNS Zone
        ↓
VNet Link
        ↓
VNet
        ↓
VM can resolve PostgreSQL hostname
```

## PostgreSQL Flexible Server

The `azurerm_postgresql_flexible_server` resource provisions the actual managed PostgreSQL server.

For VNet integration, two fields are especially important:

```text
delegated_subnet_id
private_dns_zone_id
```

`delegated_subnet_id` places PostgreSQL inside the subnet we reserved for the service.

`private_dns_zone_id` associates the PostgreSQL server with our private DNS zone so the server can be resolved privately from inside the VNet.

In total:

```text
Private DNS Zone
    = provides the private DNS namespace

VNet Link
    = makes that namespace visible to our VNet

Delegated Subnet
    = provides private network space for PostgreSQL

PostgreSQL Flexible Server
    = runs PostgreSQL inside that network boundary
```

The application then connects using the PostgreSQL hostname rather than a private IP address.

For example:

```text
synth-postgresql-server.postgres.database.azure.com
```

This is preferable to depending directly on an IP address because the hostname represents the service while Azure handles the underlying networking.

## PostgreSQL Authentication

The PostgreSQL resource also needs an administrator username and password when the server is created.

We can either:

- provide credentials ourselves, or
    
- generate credentials during provisioning
    

For this project, we are keeping a model similar to our local environment.

Secrets originate on the control machine and are supplied to the deployment rather than being hardcoded inside our Terraform configuration.

The application itself still receives the PostgreSQL credentials through environment variables.

Conceptually:

```text
Secret source
     ↓
deployment tooling
     ↓
runtime environment variables
     ↓
FastAPI
     ↓
PostgreSQL
```

This keeps the application configuration interface consistent between local development and Azure.

---

# Provisioning Redis

Redis uses a slightly different networking model.

Instead of VNet integration, Azure Managed Redis is accessed through a **private endpoint**.

For this setup we need:

1. A subnet for private endpoints
    
2. A Redis private DNS zone
    
3. A private DNS VNet link
    
4. A private endpoint
    
5. The Azure Managed Redis resource
    

## Private Endpoint Subnet

We create a dedicated subnet where Azure can place the Redis private endpoint.

The private endpoint receives a private IP address from this subnet.

Conceptually:

```text
VNet
  ↓
Private Endpoint Subnet
  ↓
Redis Private Endpoint
```

## Redis Private DNS Zone

We create the private DNS zone:

```text
privatelink.redis.azure.net
```

This zone is used by Azure Private Link for Redis.

The application does not connect directly using this `privatelink` hostname. Instead, it continues using the normal Azure Redis hostname.

For our deployment:

```text
redis-synth.northcentralus.redis.azure.net
```

Azure DNS resolves that hostname through the private endpoint when the request originates from inside our VNet.

## Redis Private DNS VNet Link

The `azurerm_private_dns_zone_virtual_network_link` resource connects the Redis private DNS zone to our VNet.

This allows the VM to resolve the Redis hostname using the private DNS configuration.

Conceptually:

```text
Redis Private DNS Zone
        ↓
VNet Link
        ↓
VNet
        ↓
VM
```

## Redis Private Endpoint

The `azurerm_private_endpoint` resource creates the actual private network connection to Azure Managed Redis.

It contains three important relationships.

### Subnet

The `subnet_id` determines where the private endpoint's network interface is created.

```text
subnet_id
    ↓
private-endpoint-subnet
```

### Private Service Connection

The `private_service_connection` connects the private endpoint to the actual Azure Managed Redis resource.

```text
Private Endpoint
      ↓
Private Service Connection
      ↓
Azure Managed Redis
```

The `private_connection_resource_id` identifies the Redis resource we are connecting to.

The `subresource_names` field identifies the Redis Private Link subresource:

```text
redisEnterprise
```

### Private DNS Zone Group

The `private_dns_zone_group` associates the private endpoint with our Redis private DNS zone.

This lets Azure maintain the DNS record that maps the Redis service to the private endpoint's IP address.

This is important because we do not want the application configuration to depend on the private endpoint's IP address.

Instead:

```text
Redis hostname
      ↓
Private DNS
      ↓
Private Endpoint IP
      ↓
Azure Managed Redis
```

## Azure Managed Redis

Finally, the `azurerm_managed_redis` resource provisions the Redis service itself.

We use:

```text
Balanced_B0
```

as the selected SKU.

We also disable public network access:

```text
public_network_access = "Disabled"
```

This means Redis can only be reached through the private networking path we created.

The complete path is therefore:

```text
FastAPI container
      ↓
VM networking
      ↓
Redis hostname
      ↓
Private DNS
      ↓
Private Endpoint
      ↓
Azure Managed Redis
```

## Redis Authentication

Like PostgreSQL, Redis requires authentication.

For Azure Managed Redis we enabled access-key authentication:

```text
access_keys_authentication_enabled = true
```

Azure generates the authentication keys when the Redis resource is created.

We do not choose the Redis access key ourselves.

Instead, we retrieve the generated key from Azure and provide it to the deployment as a secret.

Our Redis connection information therefore consists of:

```text
Hostname:
redis-synth.northcentralus.redis.azure.net

Port:
10000

TLS:
Enabled

Authentication:
Azure-generated access key
```

The resulting application connection URL follows the general form:

```text
rediss://:<access-key>@redis-synth.northcentralus.redis.azure.net:10000
```

We use `rediss://` rather than `redis://` because the Azure Managed Redis connection is encrypted with TLS.

As with PostgreSQL, the goal is that the application itself does not need to understand where the secret came from. It simply receives the completed Redis connection information through its runtime environment.


