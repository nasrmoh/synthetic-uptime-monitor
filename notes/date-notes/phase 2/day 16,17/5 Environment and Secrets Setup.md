# Environment and Secrets Setup

Our previous deployment configuration method was more complicated than necessary. We considered using Azure Key Vault as a central location for both secrets and configuration values, but decided against it because it introduced too many additional moving parts for the current project.

We did learn that Terraform can automatically provide many of the configuration values produced during infrastructure creation, such as service hostnames and generated credentials.

The revised approach is simpler:

```
Terraform
    ↓
creates infrastructure
    ↓
collects required configuration + secret values
    ↓
renders deployment .env file from a template
    ↓
Ansible
    ↓
copies deployment .env to the VM
```

Terraform will generate a separate deployment environment file using a template and the values it already knows.

Ansible will then copy that generated file onto the VM as the application's runtime `.env` file.

This keeps local development configuration separate from Azure deployment configuration while avoiding additional secret-management infrastructure for now.





