# Docker Plugin Guide

The Docker plugin (`docker` type) is used to load OCI images directly into Docker on remote systems.

## Quick Start

```yaml
post_instructions:
  plugin: docker
  options:
    docker_cmd: docker
    cleanup_tar: true
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `docker_cmd` | string | `"docker"` | Path to docker executable |
| `cleanup_tar` | bool | `true` | Delete tar file after loading |
| `use_sudo` | bool | `false` | Execute docker commands with sudo |
| `sudo_password` | string | `null` | Optional sudo password |

## Examples

### Basic Docker Host

```yaml
images:
  - nginx:latest
  - redis:7-alpine

targets:
  - host: docker.example.com
    user: ubuntu

post_instructions:
  plugin: docker
  options:
    cleanup_tar: true
```

### With Sudo

If the remote user needs sudo to run docker:

```yaml
post_instructions:
  plugin: docker
  options:
    docker_cmd: docker
    cleanup_tar: true
    use_sudo: true
    # sudo_password: "optional-if-not-using-key-based-sudo"
```

### Custom Docker Path

If docker is installed in a non-standard location:

```yaml
post_instructions:
  plugin: docker
  options:
    docker_cmd: /usr/local/bin/docker
    cleanup_tar: true
```

### Multiple Hosts

Deploy to multiple Docker hosts concurrently:

```yaml
images:
  - myapp:v1.0
  - postgres:15

targets:
  - host: docker1.example.com
    user: ubuntu
  - host: docker2.example.com
    user: ubuntu
  - host: docker3.example.com
    user: ubuntu

post_instructions:
  plugin: docker
  options:
    cleanup_tar: true
```

## How It Works

1. **Image Transfer**: Tar file containing all images is transferred to remote host
2. **Image Loading**: Docker load command executed with: `docker load < /path/to/images.tar`
3. **Verification**: Images are immediately available in Docker (check with `docker images`)
4. **Cleanup**: Tar file is removed from remote system (if `cleanup_tar: true`)

## Verification

After deployment, verify images on remote system:

```bash
# Check loaded images
ssh ubuntu@docker.example.com docker images

# Run a container from loaded image
ssh ubuntu@docker.example.com docker run -d nginx:latest
```

## Troubleshooting

### "Permission denied" error

**Problem**: User cannot access Docker daemon
**Solution**: Set `use_sudo: true` in plugin options

```yaml
post_instructions:
  plugin: docker
  options:
    use_sudo: true
```

Or add user to docker group (permanent solution):

```bash
sudo usermod -aG docker $USER
```

### "docker: not found" error

**Problem**: Docker executable not in PATH
**Solution**: Specify full path to docker command

```yaml
post_instructions:
  plugin: docker
  options:
    docker_cmd: /usr/bin/docker
```

### Images not loaded

**Problem**: docker load command failed
**Solution**: Enable verbose logging and check stderr

```bash
outrider deploy -c config.yaml -v
```

### Tar file not deleted

**Problem**: `cleanup_tar: true` but file still exists on remote
**Solution**: Verify ssh user has permission to delete in that directory, or manually delete:

```bash
ssh ubuntu@docker.example.com rm -f /tmp/images.tar
```

## Performance Notes

- **Sequential per-host**: Each host receives tar, loads, and cleans up sequentially
- **Concurrent transfers**: Multiple hosts can receive tar files concurrently (3 by default)
- **Load speed**: Docker load speed depends on image size and disk I/O on remote system

## Comparison with Other Plugins

| Plugin | Use Case | Command |
|--------|----------|---------|
| `docker` | Standalone Docker hosts | `docker load < tar` |
| `k3s_airgap` | Air-gapped K3s clusters | `ctr -n k8s.io image import` |
| `generic_ssh` | Custom scripts | User-defined command |

## Advanced: Per-Target Configuration

Override plugin options per target:

```yaml
post_instructions:
  plugin: docker  # Global default
  options:
    cleanup_tar: true

targets:
  - host: docker1.example.com
    user: ubuntu
    post_instructions:
      options:
        use_sudo: true  # Override: this host needs sudo

  - host: docker2.example.com
    user: ubuntu
    # Uses global plugin and options
```

## See Also

- [Main README](README.md)
- [Usage Examples](USAGE_EXAMPLES.md)
- [Configuration Guide](README.md#configuration-guide)
