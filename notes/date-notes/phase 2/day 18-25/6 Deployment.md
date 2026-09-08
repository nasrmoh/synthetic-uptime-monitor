# Continuous Deployment with GitHub Actions

Now that continuous integration is working, the next step is continuous deployment.

We want to prioritize automation, so instead of stopping after producing a deployable image, GitHub Actions will automatically deploy a successful build to the Azure VM.

The distinction we care about is:

```text
Continuous Integration
→ test the code

Continuous Delivery
→ produce a release that is ready to deploy

Continuous Deployment
→ automatically deploy a successful release
```

Our pipeline therefore does not stop after publishing an image to GHCR. Once the tests pass, GitHub Actions builds the new image, publishes it, connects to the deployment network, deploys it to the VM, and verifies that the application is actually ready.

## Deployment Flow

The general flow is:

```text
Push to main
    ↓
GitHub Actions runner starts
    ↓
Start local Docker Compose test environment
    ↓
Run database migrations
    ↓
Run pytest
    ↓
Build amd64 + arm64 application image
    ↓
Tag image with short commit SHA
    ↓
Push image to GHCR
    ↓
Runner authenticates to Tailscale using GitHub OIDC
    ↓
Runner joins the tailnet as tag:ci
    ↓
Runner SSHs into the Azure VM
    ↓
VM pulls the candidate SHA image
    ↓
Compose replaces the application container
    ↓
GitHub Actions checks /ready
```

If `/ready` succeeds:

```text
candidate SHA
    ↓
production tag is moved to candidate
    ↓
deployment succeeds
```

If `/ready` fails:

```text
candidate SHA fails
    ↓
production tag remains on previous known-good image
    ↓
VM redeploys production
    ↓
workflow finishes as failed
```

This gives us an important distinction between:

```text
candidate image
→ the commit we are currently testing in production

production image
→ the most recent image that successfully passed the deployment gate
```

---

# Publishing Images to GHCR

## `GITHUB_TOKEN`

To push our container image to GitHub Container Registry, the GitHub Actions runner needs to authenticate with GHCR.

GitHub automatically creates a temporary `GITHUB_TOKEN` when the workflow starts. The token exists for the workflow run and expires afterward.

We use that token as the credential when logging the Docker client into GHCR:

```yaml
- name: Log into GHCR
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

It is important to understand what `docker login` means here.

We are not signing into Docker Hub or into Docker Inc.

Instead:

```text
Docker client
    ↓
connects to ghcr.io
    ↓
GitHub verifies the supplied credentials
```

GHCR implements the Docker Registry API, so standard Docker tooling can authenticate with it and push images.

If the GHCR package was originally created through a manual push, the repository may also need to be granted access under the package's **Manage Actions access** settings.

---

# Workflow Permissions

The automatically-created `GITHUB_TOKEN` does not receive every possible permission.

We explicitly give the workflow only what it needs:

```yaml
permissions:
  contents: read
  packages: write
  id-token: write
```

These permissions have separate purposes:

```text
contents: read
→ allows the workflow to read the repository

packages: write
→ allows the workflow to push images to GHCR

id-token: write
→ allows GitHub Actions to issue an OIDC token
   for Tailscale authentication
```

---

# Keeping the Pipeline in One Job

We could split the workflow into several jobs:

```text
test
build
deploy
```

This would create stronger separation of concerns and make it immediately obvious whether testing, building, or deployment failed.

For this project, however, the pipeline is still small enough that keeping everything in one job is simpler.

GitHub Actions already stops ordinary steps when an earlier required step fails, so deployment will never happen if pytest fails.

---

# Image Versioning

Every successful CI run produces a candidate image identified by the commit that created it.

Instead of using the full Git SHA:

```text
bfbe9e1022a18c79cf0af65c53f78a533faf5309
```

we use the first seven characters:

```text
bfbe9e1
```

We generate it once:

```yaml
- name: Get short commit SHA
  id: commit
  run: echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"
```

The value is then available as:

```text
${{ steps.commit.outputs.short_sha }}
```

This same value is used when:

```text
building the image
deploying the image
promoting the image to production
```

That avoids different parts of the workflow referring to different tags.

---

# Multi-Platform Container Builds

The GitHub-hosted runner is `amd64`, while the Azure VM currently runs `arm64`.

Because of this, we build both architectures:

```text
linux/amd64
linux/arm64
```

QEMU provides emulation support:

```yaml
- name: Set up QEMU
  uses: docker/setup-qemu-action@v4
```

Buildx provides the multi-platform builder:

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v4
```

The image is then built and pushed:

```yaml
- name: Build and push container image
  uses: docker/build-push-action@v6
  with:
    context: .
    platforms: linux/amd64,linux/arm64
    push: true
    tags: ghcr.io/nasrmoh/synthetic-uptime-monitor:${{ steps.commit.outputs.short_sha }}
```

The build context is the project directory:

```text
context: .
```

This means Docker can access the files included in that build context while processing the Dockerfile.

---

# The `production` Tag

A SHA tag tells us exactly which commit produced an image:

```text
ghcr.io/nasrmoh/synthetic-uptime-monitor:bfbe9e1
```

However, we also need an easy way to identify the most recent deployment that we know worked.

For that purpose we maintain:

```text
production
```

The rule is:

```text
production always points to the most recent image
that successfully passed the production /ready check
```

We intentionally do **not** move `production` when the candidate image is first built.

Instead:

```text
build candidate
→ deploy candidate
→ verify candidate
→ only then move production
```

This is what makes rollback possible.

If a candidate fails, `production` still points to the previous working image.

---

# Compose Image Selection

The deployment Compose file cannot hardcode a specific SHA:

```yaml
image: ghcr.io/nasrmoh/synthetic-uptime-monitor:fd94ef5
```

Otherwise GitHub Actions would have no way to tell Compose which candidate image should be tested.

Instead we use:

```yaml
app:
  image: ghcr.io/nasrmoh/synthetic-uptime-monitor:${IMAGE_TAG:-production}
```

This gives us two useful behaviors.

Without specifying anything:

```bash
docker compose up -d app
```

Compose uses:

```text
production
```

During deployment:

```bash
IMAGE_TAG=bfbe9e1 docker compose up -d app
```

Compose uses:

```text
bfbe9e1
```

During rollback:

```bash
IMAGE_TAG=production docker compose up -d app
```

Compose restores the previous known-good deployment.

---

# Giving GitHub Actions Access to the VM

Publishing the image is only one part of deployment.

The GitHub Actions runner also needs a network path to the VM.

Our administrative network already uses Tailscale, so instead of exposing SSH publicly we temporarily add the GitHub runner to the same tailnet:

```text
GitHub Actions runner
    ↓
Tailscale
    ↓
Azure VM
```

There are two separate authentication problems here:

```text
1. Can the runner join the Tailscale network?

2. Once connected, can the runner authenticate to the VM over SSH?
```

We solve them independently.

---

# GitHub OIDC and Tailscale

We do not want to store a permanent Tailscale authentication key in GitHub.

Instead we use GitHub's OpenID Connect support with a Tailscale federated identity.

The trust relationship is restricted to our repository and GitHub Environment.

Our Tailscale trust credential uses a subject similar to:

```text
repo:nasrmoh/synthetic-uptime-monitor:environment:CI/CD environment
```

It receives only the permission required to create temporary authentication keys:

```text
Auth Keys
→ Read & Write
```

and those keys must assign:

```text
tag:ci
```

The resulting authentication chain is:

```text
GitHub Actions
    ↓
GitHub issues OIDC token
    ↓
Tailscale validates token
    ↓
temporary auth key is generated
    ↓
runner joins tailnet as tag:ci
```

The GitHub Environment stores the Tailscale federated identity values:

```text
TS_OAUTH_CLIENT_ID
TS_AUDIENCE
```

Despite the action input being called `oauth-client-id`, we are using it with Tailscale's federated OIDC identity rather than storing an OAuth client secret.

The workflow step is:

```yaml
- name: Connect to Tailscale Network
  uses: tailscale/github-action@v4
  with:
    oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
    audience: ${{ secrets.TS_AUDIENCE }}
    tags: tag:ci
    ping: ${{ vars.SYNTH_VM_TAILSCALE_IP }}
```

The `ping` check gives us an immediate network connectivity test before attempting SSH.

---

# SSH Authentication

Joining the Tailscale network only provides the network path:

```text
runner → VM
```

It does not authenticate the runner to Linux.

For that we created a dedicated deployment user:

```text
synth-deploy
```

and a dedicated SSH key pair.

The VM contains the public key.

GitHub stores the private key as:

```text
DEPLOY_SSH_KEY
```

The workflow writes that key into the temporary runner:

```yaml
- name: Configure SSH key
  run: |
    mkdir -p ~/.ssh

    echo "${{ secrets.DEPLOY_SSH_KEY }}" > ~/.ssh/deploy_key
    chmod 600 ~/.ssh/deploy_key
```

We also populate `known_hosts`:

```yaml
- name: Add VM SSH host key
  run: |
    ssh-keyscan -H ${{ vars.SYNTH_VM_TAILSCALE_IP }} \
      >> ~/.ssh/known_hosts
```

Then we verify access before attempting deployment:

```yaml
- name: Verify VM access
  run: |
    ssh -i ~/.ssh/deploy_key \
      synth-deploy@${{ vars.SYNTH_VM_TAILSCALE_IP }} \
      hostname
```

At this point:

```text
Tailscale
→ provides network connectivity

SSH key
→ provides host authentication
```

---

# Deploying the Candidate

The runner connects to the VM and explicitly deploys the candidate SHA:

```yaml
- name: Deploy application
  id: deploy
  continue-on-error: true
  run: |
    ssh -i ~/.ssh/deploy_key \
      synth-deploy@${{ vars.SYNTH_VM_TAILSCALE_IP }} \
      "
        cd /opt/synthetic-uptime-monitor &&

        IMAGE_TAG=${{ steps.commit.outputs.short_sha }} \
          docker compose pull app &&

        IMAGE_TAG=${{ steps.commit.outputs.short_sha }} \
          docker compose up -d app
      "
```

We pull before replacing the existing application container:

```text
pull candidate
    ↓
if successful
    ↓
replace app container
```

Because the commands are connected with `&&`, a missing image causes the deployment command to stop before Compose attempts to run it.

---

# Readiness Gate

Successfully starting a container does not prove that the application works.

For example:

```text
container running
```

does not necessarily mean:

```text
FastAPI working
PostgreSQL reachable
Redis reachable
```

This is why the deployment has a separate readiness gate.

We query:

```text
https://synthetic.nasrmoha.dev/ready
```

through the real public nginx/TLS path.

The workflow retries for approximately one minute:

```yaml
for i in {1..12}; do
  if curl --fail --silent \
    https://synthetic.nasrmoha.dev/ready > /dev/null; then

    echo "Deployment is ready"
    exit 0
  fi

  sleep 5
done
```

`curl --fail` makes HTTP error responses result in a non-zero exit code.

Therefore the gate is checking:

```text
Internet
→ HTTPS
→ nginx
→ FastAPI
→ /ready
→ PostgreSQL + Redis
```

rather than merely checking whether Docker started a container.

---

# Promoting the Candidate

If `/ready` succeeds, the candidate becomes our new known-good image.

We move the `production` tag:

```yaml
docker buildx imagetools create \
  --tag ghcr.io/nasrmoh/synthetic-uptime-monitor:production \
  ghcr.io/nasrmoh/synthetic-uptime-monitor:${{ steps.commit.outputs.short_sha }}
```

We use `buildx imagetools` rather than locally pulling, retagging, and pushing the image.

This preserves the entire multi-platform image index:

```text
production
├── linux/amd64
└── linux/arm64
```

---

# Rollback

If either deployment or readiness verification fails, `production` still points to the previous working image.

The workflow redeploys it:

```text
IMAGE_TAG=production
```

After rollback, we query `/ready` again to verify that the previous version actually restored service.

Even if rollback succeeds, the workflow still finishes as failed.

That distinction is important:

```text
service recovered
≠
new deployment succeeded
```

The failed Git commit should therefore still produce a red CI/CD run.

---

# Final CI/CD Workflow

```yaml
name: Synthetic CI Pipeline

on:
  push:
    branches:
      - main


jobs:
  test:
    runs-on: ubuntu-latest

    environment:
      name: "CI/CD environment"

    permissions:
      contents: read
      packages: write
      id-token: write

    env:
      DATABASE_URL: ${{ secrets.DATABASE_URL }}
      POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
      POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
      PROMETHEUS_URL: ${{ secrets.PROMETHEUS_URL }}
      REDIS_URL: ${{ secrets.REDIS_URL }}
      GF_SECURITY_ADMIN_USER: ${{ secrets.GF_SECURITY_ADMIN_USER }}
      GF_SECURITY_ADMIN_PASSWORD: ${{ secrets.GF_SECURITY_ADMIN_PASSWORD }}
      TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

      TEST_DATABASE_NAME: ${{ vars.TEST_DATABASE_NAME }}
      POSTGRES_DB: ${{ vars.POSTGRES_DB }}
      SCHEDULER_ENABLED: ${{ vars.SCHEDULER_ENABLED }}

    steps:
      - name: Grab the repository
        uses: actions/checkout@v4

      - name: Install Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install all dependencies
        run: pip install -r requirements.txt

      - name: Pull images for the runner
        run: docker compose pull

      - name: Start the Docker Compose Stack
        run: docker compose up --build -d

      - name: Show Docker Compose status
        run: docker compose ps -a

      - name: Show Postgres logs
        run: docker compose logs db

      - name: Wait for Postgres and Redis
        run: |
          until docker compose exec -T db pg_isready -U postgres; do sleep 1; done
          until docker compose exec -T redis redis-cli ping; do sleep 1; done

      - name: Run alembic migrations for test database
        run: ./scripts/migrate.sh

      # The project has two configuration contexts:
      #
      # 1. Compose/container configuration
      #    Services running inside Docker Compose use Docker DNS names such as:
      #      PostgreSQL -> db
      #      Redis      -> redis
      #
      # 2. Local/host configuration
      #    Processes running outside Docker, such as pytest, cannot use those
      #    Compose service names. They connect through ports published onto the
      #    runner itself, so they use localhost instead.
      #
      # Locally this distinction is handled by loading .env first and then
      # overriding selected values with .env.local.
      #
      # CI does not use those physical .env / .env.local files, so we reproduce
      # the same behavior with GitHub Actions environment scoping:
      #   - job-level env = Compose-style configuration
      #   - step-level env below = local pytest overrides
      #
      # These LOCAL_* values allow pytest to run directly on the GitHub runner
      # while PostgreSQL and Redis continue running inside Docker Compose.
      - name: Run pytest
        env:
          TEST_DATABASE_URL: ${{ secrets.LOCAL_TEST_DATABASE_URL }}
          DATABASE_URL: ${{ secrets.LOCAL_DATABASE_URL }}
          REDIS_URL: ${{ secrets.LOCAL_REDIS_URL }}
        run: pytest


      # ------------------------------------------------------------
      # Build and publish the application image
      # ------------------------------------------------------------

      # We use the first seven characters of the commit SHA as the
      # immutable version tag for this build.
      - name: Get short commit SHA
        id: commit
        run: echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - name: Log into GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # QEMU allows the amd64 GitHub runner to build the ARM64 image
      # required by the Azure VM as well as the amd64 image.
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v4

      - name: Build and push container image
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ghcr.io/nasrmoh/synthetic-uptime-monitor:${{ steps.commit.outputs.short_sha }}


      # ------------------------------------------------------------
      # Connect the runner to the deployment network
      # ------------------------------------------------------------

      - name: Connect to Tailscale Network
        uses: tailscale/github-action@v4
        with:
          oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
          audience: ${{ secrets.TS_AUDIENCE }}
          tags: tag:ci
          ping: ${{ vars.SYNTH_VM_TAILSCALE_IP }}


      # ------------------------------------------------------------
      # Configure SSH access
      # ------------------------------------------------------------

      - name: Configure SSH key
        run: |
          mkdir -p ~/.ssh

          echo "${{ secrets.DEPLOY_SSH_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key

      - name: Add VM SSH host key
        run: |
          ssh-keyscan -H ${{ vars.SYNTH_VM_TAILSCALE_IP }} \
            >> ~/.ssh/known_hosts

      - name: Verify VM access
        run: |
          ssh -i ~/.ssh/deploy_key \
            synth-deploy@${{ vars.SYNTH_VM_TAILSCALE_IP }} \
            hostname


      # ------------------------------------------------------------
      # Deploy candidate image
      #
      # The image is pulled before Compose replaces the existing app
      # container. A missing image therefore does not take down the
      # currently running version.
      # ------------------------------------------------------------

      - name: Deploy application
        id: deploy
        continue-on-error: true
        run: |
          ssh -i ~/.ssh/deploy_key \
            synth-deploy@${{ vars.SYNTH_VM_TAILSCALE_IP }} \
            "
              cd /opt/synthetic-uptime-monitor &&

              IMAGE_TAG=${{ steps.commit.outputs.short_sha }} \
                docker compose pull app &&

              IMAGE_TAG=${{ steps.commit.outputs.short_sha }} \
                docker compose up -d app
            "


      # ------------------------------------------------------------
      # Readiness gate
      #
      # A successful Docker command only proves that the container
      # started. /ready determines whether the application and its
      # dependencies are actually usable.
      # ------------------------------------------------------------

      - name: Verify deployment readiness
        id: readiness
        if: steps.deploy.outcome == 'success'
        continue-on-error: true
        run: |
          for i in {1..12}; do
            if curl --fail --silent \
              https://synthetic.nasrmoha.dev/ready > /dev/null; then

              echo "Deployment is ready"
              exit 0
            fi

            echo "Application is not ready yet..."
            sleep 5
          done

          echo "Deployment failed readiness check"
          exit 1


      # ------------------------------------------------------------
      # Successful deployment
      #
      # production always points to the most recent image that passed
      # the production readiness check.
      # ------------------------------------------------------------

      - name: Mark image as production
        if: |
          steps.deploy.outcome == 'success' &&
          steps.readiness.outcome == 'success'
        run: |
          docker buildx imagetools create \
            --tag ghcr.io/nasrmoh/synthetic-uptime-monitor:production \
            ghcr.io/nasrmoh/synthetic-uptime-monitor:${{ steps.commit.outputs.short_sha }}


      # ------------------------------------------------------------
      # Rollback
      #
      # If the candidate could not be deployed or failed /ready,
      # production still points to the previous known-good image.
      # ------------------------------------------------------------

      - name: Roll back deployment
        if: |
          always() &&
          (
            steps.deploy.outcome == 'failure' ||
            steps.readiness.outcome == 'failure'
          )
        run: |
          ssh -i ~/.ssh/deploy_key \
            synth-deploy@${{ vars.SYNTH_VM_TAILSCALE_IP }} \
            "
              cd /opt/synthetic-uptime-monitor &&

              IMAGE_TAG=production \
                docker compose pull app &&

              IMAGE_TAG=production \
                docker compose up -d app
            "


      # ------------------------------------------------------------
      # Confirm rollback restored service
      # ------------------------------------------------------------

      - name: Verify rollback readiness
        if: |
          always() &&
          (
            steps.deploy.outcome == 'failure' ||
            steps.readiness.outcome == 'failure'
          )
        run: |
          for i in {1..12}; do
            if curl --fail --silent \
              https://synthetic.nasrmoha.dev/ready > /dev/null; then

              echo "Rollback restored a healthy deployment"
              exit 0
            fi

            echo "Rollback is not ready yet..."
            sleep 5
          done

          echo "Rollback failed to restore readiness"
          exit 1


      # Even if rollback restores the application, the attempted
      # deployment itself was unsuccessful and CI should remain red.
      - name: Fail workflow after rollback
        if: |
          always() &&
          (
            steps.deploy.outcome == 'failure' ||
            steps.readiness.outcome == 'failure'
          )
        run: |
          echo "Deployment ${{ steps.commit.outputs.short_sha }} failed."
          echo "The previous production image was restored."
          exit 1
```

At this point the complete system is:

```text
GitHub
  ↓
GitHub Actions CI
  ↓
GHCR
  ↓
GitHub OIDC
  ↓
Tailscale
  ↓
SSH
  ↓
Azure VM
  ↓
Docker Compose
  ↓
nginx
  ↓
FastAPI
  ↓
/ready
  ↓
promote or rollback
```

This completes the core automated CI/CD path for the deployment.
