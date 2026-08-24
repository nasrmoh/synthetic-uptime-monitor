## GitHub Container Registry Setup

We wanted to host our container image in a registry so that the Azure virtual machine would have a stable place to pull the application image from during deployment.

The general flow we wanted was:

```text
source code
    ↓
container image
    ↓
registry
    ↓
Azure VM
```

The registry acts as the storage location between building the application and running it on the VM.

### Choosing GHCR instead of ACR

We originally planned to use Azure Container Registry (ACR), since the rest of the infrastructure is hosted in Azure.

We later switched to **GitHub Container Registry (GHCR)** because we wanted to reduce unnecessary Azure costs and keep the artifact storage simple.

This changed the architecture slightly:

```text
GitHub repository
    ↓
container image
    ↓
GitHub Container Registry
    ↓
Azure VM
```

GHCR now stores our deployable application images, while Terraform remains responsible for provisioning the Azure infrastructure.

One useful consequence of this separation is that destroying and rebuilding the Azure infrastructure does not destroy the application image stored in GHCR.

---

## Authenticating to GHCR

Before we could push an image from our development machine, Docker needed permission to write to our GitHub Container Registry namespace.

We authenticated Docker to:

```text
ghcr.io
```

using a GitHub token with the required package permissions.

Conceptually:

```text
our development machine
        ↓
GitHub authentication token
        ↓
docker login ghcr.io
        ↓
permission to push images
```

The authentication token is only a credential for accessing the registry. It is not part of the image itself and should not be stored in the Dockerfile, Terraform configuration, or Git repository.

---

## Tagging the image with the Git commit SHA

Instead of using a generic tag such as:

```text
latest
```

we tagged the image using the Git commit SHA that represented the source used for the build.

For example:

```text
ghcr.io/nasrmoh/synthetic-uptime-monitor:<commit-sha>
```

This gives us a useful relationship between the source and the deployable artifact:

```text
Git commit
    ↓
container build
    ↓
image tagged with commit SHA
    ↓
GHCR
```

This makes it easier to determine which version of the source code produced a particular container image.

The tag is still technically mutable, but we treat commit-SHA tags as immutable by convention and do not reuse them for different image contents.

---

## Architecture mismatch: `amd64` vs `arm64`

Our first image revealed an important deployment issue.

The image had been built as:

```text
linux/amd64
```

but our Azure VM uses an ARM-based VM size and runs:

```text
linux/arm64
```

So we had:

```text
container image: amd64
Azure VM:        arm64
```

GHCR could store the image successfully, but that did not mean the VM could execute it.

This showed that **registry compatibility and runtime compatibility are separate concerns**.

```text
Can GHCR store the image?
        ↓
yes

Can the target VM execute the image?
        ↓
depends on CPU architecture
```

---

## Rebuilding as a multi-platform image

Instead of maintaining separate image names for each CPU architecture, we rebuilt the application as a **multi-platform image** supporting both:

```text
linux/amd64
linux/arm64
```

Conceptually, the image tag now points to a multi-platform manifest:

```text
ghcr.io/nasrmoh/synthetic-uptime-monitor:<tag>
                    ↓
             multi-platform image
                ├── linux/amd64
                └── linux/arm64
```

This lets different machines pull the same logical image tag while Docker automatically chooses the correct platform-specific image.

For example:

```text
amd64 development machine
        ↓
same GHCR tag
        ↓
linux/amd64 image


ARM64 Azure VM
        ↓
same GHCR tag
        ↓
linux/arm64 image
```

---

## Creating a new commit tag for the multi-platform image

We did not want to reuse the SHA tag from the original amd64-only image.

That would mean the same tag had referred to two different artifacts, which would undermine the artifact-versioning convention we were trying to establish.

Instead, we created a new **empty Git commit** whose message explained that the commit existed for the multi-platform image.

The commit changed no source files, but it gave us a new unique SHA.

We then used that new SHA as the tag for the rebuilt multi-platform image:

```text
new empty Git commit
        ↓
new commit SHA
        ↓
multi-platform build
        ↓
ghcr.io/nasrmoh/synthetic-uptime-monitor:<new-sha>
```

This preserved the rule:

> One commit-SHA tag refers to one specific built artifact and is not reused.

---

## Pushing the multi-platform image

After rebuilding the image with support for both platforms, we pushed it to GHCR using the new commit-SHA tag.

At this point GHCR contained a single logical image tag with variants for:

```text
linux/amd64
linux/arm64
```

We also inspected the image manifest to verify that both platforms were actually present rather than assuming the multi-platform build had worked.

---

## Making the package public

We changed the GHCR package visibility to **public**.

This was important because the Azure VM should be able to pull the application image without storing GitHub registry credentials.

The intended deployment path is therefore:

```text
Azure VM
    ↓
docker pull
    ↓
public GHCR package
```

rather than:

```text
Azure VM
    ↓
stored GitHub credential
    ↓
private GHCR package
```

This keeps registry authentication off the VM for this public portfolio application.

A public container image does not mean the running application itself is publicly reachable. Azure networking and NSG rules still control access to the VM and its services.

---

## Testing the public image from our development machine

We did not rely only on the GitHub UI saying that the package was public.

We tested it directly.

First, we:

1. logged Docker out of GHCR
    
2. removed the local GHCR-tagged image
    
3. attempted to pull the image again
    

The pull succeeded without authentication.

That proved:

```text
no GHCR credentials
        ↓
docker pull
        ↓
public package
        ↓
pull succeeds
```

It also confirmed that the image being retrieved genuinely came back from GHCR rather than simply remaining available through the local Docker image cache.

---

## Testing from the Azure VM

We then moved to the actual target environment. The pull worked.

---

## Verifying the ARM64 image on the VM

After pulling the image successfully on the Azure VM, we inspected it and confirmed that Docker had selected:

```text
linux/arm64
```

This proved that the multi-platform image was working correctly.

The same GHCR tag can now support both environments:

```text
development machine
linux/amd64
      ↓
pull same tag
      ↓
amd64 variant


Azure VM
linux/arm64
      ↓
pull same tag
      ↓
arm64 variant
```

Docker resolves the multi-platform manifest and selects the image matching the host architecture.