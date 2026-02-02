# Production Features Guide

This guide covers the advanced production features in Outrider for enterprise deployments, CI/CD integration, and large-scale image transfers.

## Table of Contents

1. [SHA256 Cache System](#sha256-cache-system)
2. [Environment Variable Expansion](#environment-variable-expansion)
3. [Resume Capability](#resume-capability)
4. [Multiple Image Sources](#multiple-image-sources)
5. [Concurrent Upload Control](#concurrent-upload-control)
6. [CLI Commands](#cli-commands)
7. [Real-World Examples](#real-world-examples)

## SHA256 Cache System

### Purpose

Avoid redundant image compression when running deployments multiple times with the same images. The cache system tracks tar file SHA256 hashes, modification times, and file sizes.

### How It Works

1. **First run**: Creates images.tar and stores SHA256, mtime, size in `~/.outrider/cache/metadata.json`
2. **Subsequent runs**: Validates cache by checking mtime and SHA256 before compressing
3. **Cache hit**: Skips compression, saving minutes of processing time
4. **Cache miss**: Re-compresses automatically if file changed

### Configuration

Cache is **automatic by default**. Control it via CLI:

```bash
# Use cache (default)
outrider deploy -c config.yaml

# Skip cache and force re-compression
outrider deploy -c config.yaml --skip-cache

# Clear cache before deployment
outrider deploy -c config.yaml --clear-cache
```

### View Cache Statistics

```bash
outrider cache

# Output:
# Cache Statistics:
#   Directory: /home/user/.outrider/cache
#   Entries: 3
#   Total size: 2450.5 MB
#
#   Cached files:
#     - ./images.tar (2304 MB)
#     - ./prod-images.tar (1024 MB)
#     - ./staging-images.tar (512 MB)
```

### Clear Cache

```bash
# Clear all cache
outrider cache --clear-all

# Recommended: Before major version updates
outrider cache --clear-all
outrider deploy -c config.yaml
```

### Cache Location

```
~/.outrider/cache/
├── metadata.json      # Cache metadata
```

### When Cache Is Invalidated

Cache is automatically cleared if:
- Local file is modified (different mtime)
- File size changes
- SHA256 hash doesn't match

## Environment Variable Expansion

### Purpose

Securely pass secrets and configuration from environment files into YAML without hardcoding credentials.

### Features

- Load from `.env` files via CLI flag
- Load from files specified in config with `env_from`
- Direct environment variables via `env` property
- Cascading precedence with proper override behavior
- Support for variable defaults and required validation

### Syntax

| Syntax | Example | Behavior |
|--------|---------|----------|
| `$VAR` | `$IMAGE_REGISTRY` | Simple variable reference |
| `${VAR}` | `${SSH_PASSWORD}` | Explicit variable |
| `${VAR:-default}` | `${PORT:-22}` | Use default if not set |
| `${VAR:?error}` | `${API_KEY:?Required}` | Error if not set |

### Loading Environment Files

**Via CLI (multiple times):**

```bash
# Load from single file
outrider deploy -c config.yaml -e .env.prod

# Load from multiple files (cascading precedence)
outrider deploy -c config.yaml \
  -e .env.common \
  -e .env.prod \
  -e .env.secrets
```

**Via config file (env_from):**

```yaml
# Load from files in config
env_from:
  - .env.common
  - .env.prod
  - .env.secrets

images:
  - ${IMAGE_REGISTRY}/nginx:${IMAGE_TAG}
  - ${IMAGE_REGISTRY}/redis:${REDIS_VERSION}

transport:
  type: ssh
  options:
    password: ${SSH_PASSWORD}
    key_file: ${SSH_KEY_PATH}

targets:
  - host: ${PROD_HOST}
    user: ${PROD_USER}
```

**Direct environment variables (env):**

```yaml
# Direct variables in config
env:
  IMAGE_REGISTRY: "registry.example.com"
  IMAGE_TAG: "v1.2.3"

# Or as list format
env:
  - IMAGE_REGISTRY=registry.example.com
  - IMAGE_TAG=v1.2.3
```

### Precedence Order

Variables are resolved with this precedence (highest to lowest):

1. **CLI env files** (rightmost = highest priority)
   ```bash
   -e .env.common -e .env.prod -e .env.secrets
   # secrets > prod > common
   ```

2. **Config env_from** (in order)
   ```yaml
   env_from:
     - .env.common
     - .env.prod
   # prod > common
   ```

3. **Config env property** (highest in config)
   ```yaml
   env:
     OVERRIDE: "value"
   ```

4. **System environment variables** (lowest priority)

### Example .env Files

**`.env.common`:**
```bash
# Common for all environments
IMAGE_REGISTRY=registry.example.com
IMAGE_TAG=latest
SSH_KEY_PATH=~/.ssh/id_rsa
```

**`.env.prod`:**
```bash
# Production overrides
IMAGE_TAG=v1.2.3
PROD_HOST=prod.example.com
PROD_USER=deploy
SSH_PORT=2222
```

**`.env.secrets`:**
```bash
# Secrets (never commit to git!)
SSH_PASSWORD=supersecret123
API_KEY=aksk_prod_xxxxx
DB_PASSWORD=dbpass123
```

### Security Best Practices

1. **Never commit secrets** to git:
   ```bash
   echo ".env.secrets" >> .gitignore
   echo ".env.*.local" >> .gitignore
   ```

2. **Use strict file permissions**:
   ```bash
   chmod 600 .env.secrets
   ```

3. **Use CI/CD secret management**:
   ```bash
   # GitHub Actions example
   - name: Deploy with Outrider
     env:
      SSH_PASSWORD: ${{ secrets.SSH_PASSWORD }}
      API_KEY: ${{ secrets.API_KEY }}
     run: |
       echo "SSH_PASSWORD=$SSH_PASSWORD" >> .env.secrets
       echo "API_KEY=$API_KEY" >> .env.secrets
       outrider deploy -c config.yaml -e .env.secrets
   ```

## Resume Capability

### Purpose

Resume interrupted file transfers without starting from scratch, saving hours on unstable networks or with large files.

### How It Works

1. **Transfer starts**: Progress tracked in `~/.outrider/resume/`
2. **Connection drops**: Progress saved with bytes transferred
3. **Retry**: Validates file hasn't changed, resumes from last position
4. **Success**: Resume file deleted

### Resume State Tracking

Files are tracked automatically at `~/.outrider/resume/{resume_key}.json`:

```json
{
  "local_path": "./images.tar",
  "remote_host": "prod.example.com",
  "remote_path": "/tmp/images.tar",
  "transferred_bytes": 524288000,
  "total_bytes": 1073741824,
  "percentage": 48.83,
  "file_size": 1073741824,
  "local_mtime": 1706700123.456
}
```

### Viewing Pending Transfers

```bash
outrider resume

# Output:
# Resume Statistics:
#   Directory: /home/user/.outrider/resume
#   Pending transfers: 2
#
#   Pending transfers:
#     - images-prod.json (48.83% - 512MB/1GB)
#     - images-staging.json (23.15% - 256MB/1GB)
```

### Cleanup Old Resumes

Resume files older than 7 days are automatically removed:

```bash
outrider resume --cleanup-old

# Or let them auto-cleanup during next deploy
outrider deploy -c config.yaml
```

### When Resume Is NOT Used

Resume is skipped if:
- File size changed locally
- Local file modification time changed
- Connection succeeded on first try
- Explicitly using `--skip-cache` flag

## Multiple Image Sources

### Purpose

Load container images from multiple sources and automatically deduplicate:
- Direct config `images` property
- External files via `images_from`
- Useful for monorepos, multi-team setups, dynamic image lists

### Configuration

**Direct list (images):**

```yaml
images:
  - nginx:latest
  - redis:7-alpine
  - postgres:15
```

**From files (images_from):**

```yaml
images_from:
  - images/core.txt
  - images/optional.txt
  - /tmp/generated-images.txt
```

**Mixed (both):**

```yaml
images:
  - nginx:latest

images_from:
  - images/generated.txt
  - images/optional.txt

# Result: All images combined and deduplicated
```

### File Format

Images in files must be **whitespace-separated** (newlines, tabs, or spaces):

**`images/core.txt`:**
```
nginx:latest
redis:7-alpine
postgres:15
```

Or all on one line:
```
nginx:latest redis:7-alpine postgres:15
```

Or mixed:
```
nginx:latest redis:7-alpine
postgres:15
    mariadb:lts
```

### Deduplication

If the same image appears in multiple sources, it's automatically deduplicated:

```yaml
images:
  - nginx:latest
  - redis:7-alpine

images_from:
  - images/team-a.txt  # Contains: nginx:latest, postgres:15
  - images/team-b.txt  # Contains: redis:7-alpine, mysql:8

# Result (deduplicated and sorted):
# - mariadb:lts
# - mysql:8
# - nginx:latest
# - postgres:15
# - redis:7-alpine
```

### Real-World Use Case

**Monorepo with team images:**

```yaml
# config.yaml
images_from:
  - images/shared.txt         # Base images used by all
  - images/team-platform.txt  # Platform team images
  - images/team-api.txt       # API team images
  - images/optional.txt       # Optional/experimental
```

**`images/shared.txt`:**
```
alpine:latest
ubuntu:22.04
nginx:latest
```

**`images/team-platform.txt`:**
```
prometheus:latest
grafana:latest
elasticsearch:8
```

**`images/team-api.txt`:**
```
node:18-alpine
python:3.11-slim
redis:7-alpine
```

### Generate Images Dynamically

```bash
#!/bin/bash
# Generate image list for this environment

{
  # Base images
  echo "alpine:latest"
  echo "ubuntu:22.04"

  # Get images from container registry
  registry-cli list my-registry:5000 | grep 'v1\.'
} > /tmp/current-images.txt

# Now deploy with dynamic images
outrider deploy -c config.yaml
```

## Concurrent Upload Control

### Purpose

Control how many file transfers happen in parallel to manage network/CPU load.

### Configuration

**Via CLI (default: 2):**

```bash
# Use default (2 concurrent)
outrider deploy -c config.yaml

# Increase for faster deployment with good network
outrider deploy -c config.yaml --max-concurrent-uploads 5

# Decrease for limited bandwidth
outrider deploy -c config.yaml --max-concurrent-uploads 1
```

### Valid Range

- Minimum: 1 (sequential uploads)
- Maximum: 10 (aggressive parallelism)
- Default: 2 (stable and performant)

### Choosing the Right Value

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Slow/unstable network | 1-2 | Fewer connections reduce timeouts |
| Local datacenter | 3-5 | Good bandwidth, safe parallelism |
| High-performance network | 5-10 | Maximize throughput |
| CI/CD pipeline | 2-3 | Balance speed and stability |
| Large tar files (>500MB) | 1-2 | Prevent resource exhaustion |
| Many targets (>10) | 2-3 | Manage connection pools |

### Performance Impact

Benchmark example (3GB tar file, 10 targets):

```
--max-concurrent-uploads 1:  45 minutes
--max-concurrent-uploads 2:  25 minutes  (default)
--max-concurrent-uploads 3:  18 minutes
--max-concurrent-uploads 5:  12 minutes
--max-concurrent-uploads 10: 8 minutes (but higher failure risk)
```

## CLI Commands

### Deploy

```bash
# Basic deployment
outrider deploy -c config.yaml

# With environment variables
outrider deploy -c config.yaml -e .env.prod -e .env.secrets

# Verbose output
outrider deploy -c config.yaml -v

# Advanced options
outrider deploy -c config.yaml \
  -e .env.prod \
  --skip-cache \
  --max-concurrent-uploads 5 \
  --skip-host-verification
```

### Validate

```bash
# Validate configuration
outrider validate -c config.yaml

# With environment expansion
outrider validate -c config.yaml -e .env.prod
```

### Cache

```bash
# Show cache statistics
outrider cache

# Clear all cache
outrider cache --clear-all
```

### Resume

```bash
# Show pending transfers
outrider resume

# Cleanup old resume files
outrider resume --cleanup-old
```

## Real-World Examples

### Example 1: Multi-Environment Deployment

**Directory structure:**
```
.
├── config.yaml
├── .env.common
├── .env.prod
├── .env.prod.secrets (in .gitignore)
├── .env.staging
└── images/
    ├── core.txt
    ├── optional.txt
```

**`config.yaml`:**
```yaml
env_from:
  - .env.common

images_from:
  - images/core.txt
  - images/optional.txt

runtime:
  type: docker

transport:
  type: ssh
  options:
    user: ${SSH_USER}
    password: ${SSH_PASSWORD}

targets:
  - host: ${TARGET_HOST}
    port: ${SSH_PORT}
```

**`.env.common`:**
```bash
SSH_USER=deploy
SSH_PORT=22
```

**`.env.prod`:**
```bash
TARGET_HOST=prod.example.com
IMAGE_TAG=v1.2.3
```

**`.env.prod.secrets`:**
```bash
SSH_PASSWORD=prod_secret_pass
```

**Deployment:**
```bash
# Production
outrider deploy -c config.yaml \
  -e .env.prod \
  -e .env.prod.secrets \
  --max-concurrent-uploads 3

# Staging
outrider deploy -c config.yaml \
  -e .env.staging \
  --max-concurrent-uploads 2
```

### Example 2: Monorepo with Dynamic Images

**Generate images list from git tags:**

```bash
#!/bin/bash
# scripts/generate-images.sh

# Get all image tags pushed since last deployment
git log --oneline -1 -- images/ | awk '{print $1}' > /tmp/last_commit

{
  # Base images
  grep '^' images/base.txt 2>/dev/null || echo "alpine:latest"

  # Services
  for service in services/*; do
    docker-compose -f "$service/docker-compose.yml" config \
      | grep 'image:' | awk -F': ' '{print $2}' | tr -d "'"
  done

  # Platform components
  registry-cli list registry.internal/prod | grep -E "v[0-9]"
} | sort -u > /tmp/deployment-images.txt

echo "Generated $(wc -l < /tmp/deployment-images.txt) unique images"
```

**Config:**
```yaml
env_from:
  - .env.prod

images_from:
  - /tmp/deployment-images.txt

post_instructions:
  plugin: k3s_airgap
```

**Deploy:**
```bash
#!/bin/bash
scripts/generate-images.sh
outrider deploy -c config.yaml \
  -e .env.prod \
  --max-concurrent-uploads 4
```

### Example 3: CI/CD Pipeline Integration

**GitHub Actions:**

```yaml
name: Deploy Images to K3s

on:
  push:
    branches: [main]
    paths: ['images/**', 'config.yaml']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Outrider
        run: pip install -e .

      - name: Create secrets file
        run: |
          cat > .env.secrets << EOF
          SSH_PASSWORD=${{ secrets.K3S_SSH_PASSWORD }}
          API_KEY=${{ secrets.REGISTRY_API_KEY }}
          EOF
          chmod 600 .env.secrets

      - name: Validate configuration
        run: |
          outrider validate -c config.yaml -e .env.secrets

      - name: Show cache status
        run: outrider cache

      - name: Deploy images
        run: |
          outrider deploy \
            -c config.yaml \
            -e .env.production \
            -e .env.secrets \
            --max-concurrent-uploads 4 \
            -v

      - name: Cleanup
        if: always()
        run: rm -f .env.secrets

      - name: Notify slack
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {"text": "Image deployment failed"}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

For more information, see:
- [README.md](README.md) - Overview and quick start
- [SSH_AUTHENTICATION_GUIDE.md](SSH_AUTHENTICATION_GUIDE.md) - SSH configuration
- [DOCKER_PLUGIN_GUIDE.md](DOCKER_PLUGIN_GUIDE.md) - Docker plugin reference
