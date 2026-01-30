# Outrider Quick Start Guide

Get up and running with Outrider in 5 minutes.

## 1. Install

```bash
# Clone the repository
git clone <repo-url>
cd outrider

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
outrider --version
```

## 2. Create Configuration

Create a file named `config.yaml`:

```yaml
images:
  - nginx:latest
  - redis:7-alpine

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  - host: 192.168.1.10
    user: ubuntu
    port: 22

post_instructions:
  plugin: k3s_airgap
  options:
    cleanup_tar: true
```

**Required fields:**
- `images`: List of OCI images to pull
- `targets`: List of remote systems with `host`, `user`, and `port`

**Optional fields:**
- `runtime`: Container runtime (default: Docker)
- `transport`: Network protocol (default: SSH)
- `post_instructions`: What to do with images on remote systems
- `output_tar`: Local tar filename (default: `images.tar`)
- `remote_tar_path`: Remote tar path (default: `/tmp/images.tar`)

## 3. Validate Configuration

```bash
outrider validate -c config.yaml
```

Expected output:
```
✓ Configuration is valid
  Images: 2
  Targets: 1
  Post-instruction plugin: k3s_airgap
```

## 4. Deploy

```bash
outrider deploy -c config.yaml
```

For verbose output:
```bash
outrider deploy -c config.yaml -v
```

## What Happens

1. **Pull**: Downloads images from Docker registry
2. **Compress**: Creates `images.tar` with all images
3. **Transfer**: Sends tar file to each remote system via SSH
4. **Execute**: Runs post-instructions on each system
5. **Cleanup**: Removes tar files (if configured)

## Common Use Cases

### Air-gapped Kubernetes

```yaml
post_instructions:
  plugin: k3s_airgap
  options:
    k3s_path: /usr/local/bin/k3s
    containerd_path: /run/k3s/containerd/containerd.sock
    cleanup_tar: true
```

### Docker

```yaml
post_instructions:
  plugin: generic_ssh
  options:
    command: docker load < {tar_path} && rm {tar_path}
```

### Just Transfer Files

```yaml
# No post_instructions section
```

## Troubleshooting

### SSH Connection Issues

```bash
# Test SSH connection
ssh -i ~/.ssh/id_rsa ubuntu@192.168.1.10 whoami

# Fix permissions if needed
chmod 600 ~/.ssh/id_rsa
```

### Docker Pull Fails

```bash
# Test locally
docker pull nginx:latest

# Check Docker daemon
docker ps
```

### Enable Verbose Logging

```bash
outrider deploy -c config.yaml -v
```

## Next Steps

- Read [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for advanced examples
- Read [README.md](README.md) for complete documentation
- Explore [examples/](examples/) directory for configuration templates

## Help

```bash
outrider --help
outrider deploy --help
outrider validate --help
```

---

**Need help?** Check the full documentation in [README.md](README.md)
