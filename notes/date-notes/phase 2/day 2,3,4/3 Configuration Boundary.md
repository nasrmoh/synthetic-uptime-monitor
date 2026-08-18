# Configuration Boundary

## Environment Variable Classification

|Variable|Category|Compose / local development value|Local pytest behaviour|
|---|---|---|---|
|`POSTGRES_USER`|Secret|`<<placeholder>>`|Overridden by `.env.local`|
|`POSTGRES_PASSWORD`|Secret|`<<placeholder>>`|Overridden by `.env.local`|
|`POSTGRES_DB`|Ordinary config|`db`|Overridden by `.env.local`|
|`TEST_DATABASE_NAME`|Ordinary config|`test_db`|Overridden by `.env.local`|
|`REDIS_URL`|Ordinary config|`redis://redis:6379`|Overridden with `redis://localhost:6379`|
|`DATABASE_URL`|Ordinary config|`postgresql://...@db:5432/${POSTGRES_DB}`|Overridden with `...@localhost:5432/${POSTGRES_DB}`|
|`TEST_DATABASE_URL`|Ordinary config|`postgresql://...@db:5432/${TEST_DATABASE_NAME}`|Overridden with `...@localhost:5432/${TEST_DATABASE_NAME}`|
|`SCHEDULER_ENABLED`|Ordinary config|`True`|Inherited unchanged|
|`GF_SECURITY_ADMIN_USER`|Secret|`<<placeholder>>`|Inherited unchanged|
|`GF_SECURITY_ADMIN_PASSWORD`|Secret|`<<placeholder>>`|Inherited unchanged|
|`PROMETHEUS_URL`|Ordinary config|`http://prometheus:9090`|Inherited unchanged|

### Local pytest configuration

`conftest.py` loads `.env` first, followed by `.env.local` with `override=True`.

The purpose of `.env.local` is to replace values that depend on whether the application is running inside Docker Compose or directly on the host.

For example:

```text
Compose:
redis://redis:6379

Local pytest:
redis://localhost:6379
```

The database connection follows the same pattern:

```text
Compose:
PostgreSQL host = db

Local pytest:
PostgreSQL host = localhost
```

Values that do not require a different local-test configuration continue to come from `.env`.

The important boundary is that the application itself does not care which file supplied the value. It consumes the resulting environment variable.

---

## Deployment-Provided Secrets

The deployed application will continue to receive secrets as **runtime environment variables**.

This is the same interface the application already uses locally:

```python
os.environ["..."]
```

What changes between environments is not how the application reads configuration, but **where the value originates before becoming an environment variable**.

### Key Vault Decision

Azure Key Vault will not initially be used for application secrets.

Using Key Vault would require the application or deployment process to introduce additional concerns such as:

- Azure authentication
    
- authorization to the vault
    
- network access to the vault
    
- Azure SDK integration if the application retrieves secrets directly
    
- another dependency that can fail during startup
    

For the current architecture, this additional complexity does not provide enough benefit over securely injecting the required values into the application's runtime environment.

Terraform will also not read or provision application secret values.

This keeps secrets out of Terraform resource attributes and avoids the risk of secret values being written into Terraform state.

---

## Secret Flow by Environment

### Local Development

Secrets are entered manually into:

```text
.env
.env.local
```

Both files remain gitignored.

The files are local convenience mechanisms. The application depends on the **environment variables they produce**, not on the files themselves.

### Manual Azure Deployment

Once Ansible is responsible for configuring the VM, deployment secrets will be stored in an **Ansible Vault-encrypted file**.

The encrypted file can be committed to the repository while the Vault password remains outside the repository.

The deployment flow becomes:

```text
Ansible Vault encrypted values
        ↓
ansible-playbook
        ↓
decrypt during deployment
        ↓
VM / Compose runtime environment
        ↓
application
```

Ansible can either:

- write an environment file consumed by Compose, or
- otherwise inject the required values into the deployment environment

The exact implementation can be decided when the Ansible configuration is built.

### CI/CD Deployment

Once continuous deployment is introduced, the source of deployment secrets changes to **GitHub Actions Secrets**.

Conceptually:

```text
GitHub Actions Secrets
        ↓
CD workflow
        ↓
deployment process
        ↓
VM / Compose runtime environment
        ↓
application
```

The application configuration interface does not change.

Whether secrets originate from `.env`, Ansible Vault, or GitHub Actions Secrets, the application continues to consume the same environment variables at startup.

This gives a consistent configuration boundary:

```text
secret/configuration source
        ↓
environment variable
        ↓
application
```

---

## Secret Source Decisions

|Secret|Local source|Initial deployed source|Later CI/CD source|
|---|---|---|---|
|`POSTGRES_USER`|`.env`|Ansible Vault|GitHub Actions Secrets|
|`POSTGRES_PASSWORD`|`.env`|Ansible Vault|GitHub Actions Secrets|
|`GF_SECURITY_ADMIN_USER`|`.env`|Ansible Vault|GitHub Actions Secrets|
|`GF_SECURITY_ADMIN_PASSWORD`|`.env`|Ansible Vault|GitHub Actions Secrets|

---

## Resulting Configuration Boundary

The intended rule is:

> The application consumes environment variables. `.env`, Ansible Vault, and GitHub Actions Secrets are mechanisms for supplying those variables, not dependencies of the application itself.

This keeps local development simple while allowing the deployment mechanism to change later without requiring application-level configuration changes.