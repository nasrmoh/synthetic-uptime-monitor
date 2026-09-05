# Application Directory, Files, Users, and Permissions

We have now configured Docker and Docker Compose on the VM using Ansible.

The VM starts as a mostly bare Linux machine, so we need a predictable location for the files required to run the Synthetic Uptime Monitor.

We will use:

```
/opt/synthetic-uptime-monitor
```

`/opt` is commonly used for application software and deployment-related files that are not part of the operating system itself.

Our deployment directory will therefore look roughly like:

```
/opt/synthetic-uptime-monitor/
├── docker-compose.yml
├── .env
├── prometheus.yml
└── monitoring/
    ├── prometheus/
    ├── grafana/
    └── alertmanager/
```

## What Files Does the VM Actually Need?

To determine what needs to exist on the VM, we can look at the deployment Compose configuration.

Originally, our local development Compose file included:

```
volumes:
  - .:/app
```

This mounted the source code from the host machine into the application container.

That was useful during development because changes to our source code were immediately reflected inside the container.

For deployment, however, we now use the prebuilt application image stored in GHCR:

```
image: ghcr.io/nasrmoh/synthetic-uptime-monitor:fd94ef5
```

The application source code is already contained inside that image.

Therefore, we no longer need:

```
- .:/app
```

on the deployment VM.

The VM only needs the deployment configuration required to start and configure the containers.

## Docker Volumes and Bind Mounts

When reading a Compose mount such as:

```
source:destination
```

the left side refers to the source and the right side refers to the location inside the container.

For example:

```
./prometheus.yml:/etc/prometheus/prometheus.yml
```

means:

```
VM
./prometheus.yml

        ↓ mounted into

Prometheus container
/etc/prometheus/prometheus.yml
```

Because Compose is run from:

```
/opt/synthetic-uptime-monitor
```

the source resolves to:

```
/opt/synthetic-uptime-monitor/prometheus.yml
```

We therefore need to make sure that any host-side files referenced by Compose actually exist on the VM.

### Prometheus

Prometheus uses:

```
./prometheus.yml:/etc/prometheus/prometheus.yml
./monitoring/prometheus/rules:/etc/prometheus/rules
```

Therefore the VM needs:

```
prometheus.yml
monitoring/prometheus/rules/
```

### Grafana

Grafana uses several configuration files:

```
./monitoring/grafana/provisioning/datasources/prometheus-datasources.yml:/etc/grafana/provisioning/datasources/prometheus-datasources.yml

./monitoring/grafana/provisioning/dashboards/dashboard.yml:/etc/grafana/provisioning/dashboards/dashboard.yml

./monitoring/grafana/dashboards/grafana-dashboard.json:/etc/grafana/dashboards/grafana-dashboard.json
```

These files therefore need to exist under the deployment's `monitoring/` directory.

### Alertmanager

Alertmanager uses:

```
./monitoring/alertmanager/alertmanager-config.yml:/etc/alertmanager/alertmanager.yml
```

It also uses:

```
alertmanager_data:/alertmanager
```

The first is a bind mount from the VM and therefore requires us to provide the configuration file.

The second is a Docker-managed named volume. Docker creates and manages it for us, so we do not need to create an `/opt` directory for it manually.

### PostgreSQL

Our original local Compose setup used:

```
postgres_data:/var/lib/postgresql
```

because PostgreSQL ran as a local container.

The Azure deployment is moving PostgreSQL to Azure Database for PostgreSQL Flexible Server, so the deployment VM will not need the local PostgreSQL container or its `postgres_data` volume.

## Environment Files

Our local development environment uses both:

```
.env
.env.local
```

`.env.local` primarily exists to support local development and testing.

The Azure VM is a deployment environment. Regular application tests should normally run before deployment rather than requiring the deployed VM to reproduce our local testing environment.

Therefore, we do not need:

```
.env.local
```

on the deployment VM.

We do still need:

```
.env
```

because Docker Compose uses it to obtain the configuration and environment variables required by the deployed services.

For now, this file is copied onto the VM by Ansible and remains excluded from Git.

## Required Deployment Files

The files Ansible needs to deploy are therefore:

```
docker-compose.yml
.env
prometheus.yml
monitoring/
```

They will all live underneath:

```
/opt/synthetic-uptime-monitor
```

---

# Setting Users and Groups

## Application User

We create a separate user called:

```
synth-app-user
```

The intended separation is:

```
synth-admin
= human administrator

synth-app-user
= application/deployment execution identity
```

`synth-admin` is the user we log into when administering the VM.

`synth-app-user` represents the identity associated with running the deployed application.

To run Docker without `sudo`, `synth-app-user` belongs to the:

```
docker
```

group.

> Membership in the `docker` group effectively gives a user root-level control over the host. For example, a Docker user can start a container with access to the host filesystem.

Because of this, `synth-app-user` should not be considered a strong security boundary from root.

We still keep the user separate because it gives us a clearer separation of responsibilities between:

```
human administration
```

and:

```
application execution
```

## Shared Application Group

We also create:

```
synth-app
```

Both users belong to this group:

```
synth-app
├── synth-admin
└── synth-app-user
```

This allows both users to receive the same normal filesystem access to the deployment.

Administrative modifications are still performed by root, normally through Ansible or `sudo`.

---

# File and Directory Permissions

## Main Application Directory

Our deployment directory is:

```
/opt/synthetic-uptime-monitor
```

Before choosing its permissions, we need to remember that directory permission bits behave differently from normal file permissions.

For a directory:

```
r = list the directory contents
w = create, delete, or rename entries
x = enter and traverse the directory
```

We want members of `synth-app` to be able to inspect and traverse the deployment, but not modify it.

Therefore:

```
read     yes
write    no
execute  yes
```

which gives:

```
r-x = 5
```

Unrelated users do not need access:

```
--- = 0
```

The directory is owned by:

```
root:synth-app
```

meaning:

```
owner = root
group = synth-app
```

Root has:

```
rwx = 7
```

The final permission is therefore:

```
0750
```

or:

```
root        rwx
synth-app   r-x
others      ---
```

Conceptually:

```
root
→ full control

synth-admin
→ read and traverse normally
→ use sudo for administrative changes

synth-app-user
→ read and traverse normally
→ cannot modify deployment files

other users
→ no access
```

---

# Container Configuration Permissions

Originally, we applied the same restrictive permission policy to the entire monitoring tree:

```
Directories: 0750
Files:       0640
```

This worked for our host users because both `synth-admin` and `synth-app-user` belong to `synth-app`.

However, when we started the containers, Alertmanager failed with:

```
permission denied
```

This exposed an important detail.

The processes running inside our containers have their own Linux UIDs and GIDs.

They are not automatically members of the host's:

```
synth-app
```

group.

For example, a configuration file with:

```
root:synth-app 0640
```

means:

```
root        rw-
synth-app   r--
others      ---
```

A container process that is neither `root` nor a member of `synth-app` falls into:

```
others
```

and therefore cannot read the file.

## Revised Monitoring Permissions

The monitoring configuration does not contain our deployment secrets, so we can allow container processes to read it.

Monitoring directories use:

```
0755
```

which means:

```
root        rwx
synth-app   r-x
others      r-x
```

Monitoring configuration files use:

```
0644
```

which means:

```
root        rw-
synth-app   r--
others      r--
```

This allows container processes to read the configuration while still preventing them from modifying it through normal host filesystem permissions.

Where appropriate, these bind mounts should also be mounted read-only using:

```
:ro
```

For example:

```
./monitoring/alertmanager/alertmanager-config.yml:/etc/alertmanager/alertmanager.yml:ro
```

This gives us two protections:

```
0644
→ container process can read the host configuration

:ro
→ container cannot modify the bind-mounted configuration
```

---

# `.env` Permissions

The `.env` file is different because it contains deployment configuration and secrets.

It does not need to be directly bind-mounted into the containers. Docker Compose reads the file and passes the appropriate values into the containers as environment variables.

Therefore, `.env` remains:

```
root:synth-app 0640
```

or:

```
root        rw-
synth-app   r--
others      ---
```

We do **not** make `.env` `0644`, because that would allow every local user on the VM to read its secrets.

---

# Final Permission Policy

We therefore no longer use one recursive permission policy for everything.

Instead, permissions depend on what the file is used for.

```
Main deployment directory
/opt/synthetic-uptime-monitor
→ root:synth-app
→ 0750

Host-side deployment files
docker-compose.yml
→ root:synth-app
→ 0640

Secrets / environment configuration
.env
→ root:synth-app
→ 0640

Container-readable monitoring directories
monitoring/
→ root:synth-app
→ 0755

Container-readable monitoring config
*.yml, *.json, rules, provisioning files
→ root:synth-app
→ 0644

Prometheus configuration
prometheus.yml
→ root:synth-app
→ 0644
```

The main lesson from the adjustment is that we have to consider **two different permission environments**:

```
Host users
├── root
├── synth-admin
└── synth-app-user

Container processes
├── Prometheus user
├── Grafana user
└── Alertmanager user
```

The host users can share access through `synth-app`, but container processes do not automatically inherit that group membership.

Our deployment permissions therefore need to allow the containers to read the configuration they are explicitly given, while keeping sensitive files such as `.env` restricted.