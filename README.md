# Outrider - OCI Image Transfer Tool

Outrider automates the process of pulling OCI/Docker images from an online machine, compressing them, and deploying them to air-gapped or remote systems with extensible architecture for different container runtimes, transport protocols, and post-deployment actions.

## Features

- **Container Runtime Abstraction**: Support for Docker (extensible to Podman, containerd, etc.)
- **Transport Abstraction**: SSH/SCP transport with extensible architecture for other protocols
- **Plugin System**: Extensible post-instruction plugins for various deployment scenarios
- **Built-in Plugins**:
  - `k3s_airgap`: Import images into air-gapped K3s clusters
  - `docker`: Load images into Docker on remote systems
  - `generic_ssh`: Execute arbitrary SSH commands for custom deployments
- **Batch Operations**: Deploy to multiple remote systems simultaneously
- **Configuration-driven**: YAML-based configuration for repeatability

## Installation

### Requirements
- Python 3.8+
- Docker or other OCI-compatible container runtime
- SSH access to target systems

### Setup

```bash
# Clone or download the project
cd outrider

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
outrider --version
```

## Quick Start

### 1. Create a Configuration File

Start with the provided example:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your specific needs:

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

### 2. Validate Configuration

```bash
outrider validate -c config.yaml
```

### 3. Deploy Images

```bash
outrider deploy -c config.yaml
```

For verbose output:

```bash
outrider deploy -c config.yaml -v
```

## Configuration Guide

### Top-level Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `images` | list | Yes | OCI images to pull and transfer |
| `runtime` | dict | No | Container runtime configuration |
| `transport` | dict | No | Network transport configuration |
| `targets` | list | Yes | Remote systems to deploy to |
| `output_tar` | string | No | Local tar file path (default: `images.tar`) |
| `remote_tar_path` | string | No | Remote tar file path (default: `/tmp/images.tar`) |
| `post_instructions` | dict | No | Post-deployment instructions |

### Runtime Configuration

```yaml
runtime:
  type: docker  # Required: runtime type
  options:
    cmd: docker  # Docker command path (default: 'docker')
```

**Supported runtime types:**
- `docker`: Docker daemon (default)

### Transport Configuration

```yaml
transport:
  type: ssh  # Required: transport type
  options:
    key_file: ~/.ssh/id_rsa    # SSH private key path
    # password: "ssh-password"  # Alternative: SSH password
```

**Supported transport types:**
- `ssh`: SSH/SCP (default)

### Targets Configuration

```yaml
targets:
  - host: hostname-or-ip       # Required: target host
    user: username             # Optional: SSH user (default: 'root')
    port: 22                   # Optional: SSH port (default: 22)
```

### Post-Instructions Plugins

#### K3s Air-gap Plugin

For importing images into air-gapped K3s clusters:

```yaml
post_instructions:
  plugin: k3s_airgap
  options:
    k3s_path: /usr/local/bin/k3s           # K3s executable path
    containerd_path: /run/k3s/containerd/containerd.sock  # Containerd socket
    cleanup_tar: true                      # Remove tar after import
```

#### Docker Plugin

For loading images into Docker on remote systems:

```yaml
post_instructions:
  plugin: docker
  options:
    docker_cmd: docker           # Docker command path (default: 'docker')
    cleanup_tar: true            # Remove tar after loading
    use_sudo: false              # Use sudo if needed (default: false)
    # sudo_password: "password"  # Optional: password for sudo
```

#### Generic SSH Plugin

For custom deployment scripts:

```yaml
post_instructions:
  plugin: generic_ssh
  options:
    command: |
      # {tar_path} is replaced with actual path
      docker load < {tar_path}
      rm {tar_path}
```

#### No Post-instructions

To only transfer files without executing commands:

```yaml
post_instructions: null
```

## Use Cases

### Air-gapped K3s Cluster

```yaml
images:
  - k3s.io/rancher/k3s-payload:v1.28.0

targets:
  - host: k3s-node-1
    user: root

post_instructions:
  plugin: k3s_airgap
  options:
    cleanup_tar: true
```

### Docker Swarm Deployment

```yaml
post_instructions:
  plugin: generic_ssh
  options:
    command: docker load < {tar_path} && rm {tar_path}
```

### Multiple K8s Clusters

```yaml
targets:
  - host: cluster-1-node
    user: ubuntu
  - host: cluster-2-node
    user: ubuntu
  - host: cluster-3-node
    user: ubuntu

post_instructions:
  plugin: k3s_airgap
```

## Workflow

1. **Pull Images**: Download images from registry using configured container runtime
2. **Compress**: Save all images to a single tar file
3. **Transfer**: Upload tar file to each remote target via SSH/SCP
4. **Execute**: Run post-instructions on each target (if configured)
5. **Cleanup**: Remove tar files from remote systems (if configured)

## Architecture

### Components

- **Runtime**: Container runtime abstraction (DockerRuntime)
- **Transport**: Network transport protocol (SSHTransport)
- **Plugins**: Post-instruction handlers (K3sAirgapPlugin, GenericSSHPlugin)
- **Orchestrator**: Coordinates the entire workflow
- **CLI**: Command-line interface

### Extensibility

All core components are designed to be extended:

```python
# Add new runtime
class PodmanRuntime(BaseRuntime):
    def pull_image(self, image_name: str) -> bool:
        pass
    # ... implement other methods

# Add new plugin
class MyCustomPlugin:
    def __init__(self, transport: BaseTransport):
        self.transport = transport

    def execute(self, remote_host, tar_path, options):
        pass
```

## Troubleshooting

### Authentication Fails

```bash
# Test SSH connectivity
ssh -i ~/.ssh/id_rsa user@host

# Verify key permissions
chmod 600 ~/.ssh/id_rsa
```

### Docker Pull Fails

```bash
# Check Docker daemon
docker ps

# Check registry access
docker pull nginx:latest

# Enable verbose logging
outrider deploy -c config.yaml -v
```

### K3s Import Fails

```bash
# Verify K3s cluster is running
sudo k3s kubectl get nodes

# Check containerd socket
ls -l /run/k3s/containerd/containerd.sock

# Verify tar file transfer
ssh user@host ls -lh /tmp/images.tar
```

## Examples

See [config.example.yaml](config.example.yaml) for complete configuration examples.

## Development

### Project Structure

```
outrider/
├── outrider/
│   ├── cli.py              # CLI entry point
│   ├── core/
│   │   ├── config.py       # Configuration management
│   │   └── orchestrator.py # Workflow orchestration
│   ├── runtime/
│   │   ├── base.py         # Runtime abstraction
│   │   └── docker.py       # Docker implementation
│   ├── transport/
│   │   ├── base.py         # Transport abstraction
│   │   └── ssh.py          # SSH/SCP implementation
│   └── plugins/
│       ├── base.py         # Plugin abstraction
│       ├── k3s_airgap.py   # K3s plugin
│       └── generic_ssh.py  # Generic SSH plugin
├── setup.py
└── requirements.txt
```

### Adding a New Plugin

1. Create a new file in `outrider/plugins/`
2. Implement the plugin interface
3. Register in `outrider/plugins/__init__.py`
4. Use in configuration with `plugin: your_plugin_name`

Example:

```python
# outrider/plugins/my_plugin.py
from outrider.transport.base import BaseTransport, RemoteHost

class MyPlugin:
    def __init__(self, transport: BaseTransport):
        self.transport = transport

    def execute(self, remote_host: RemoteHost, tar_path: str, options: dict) -> bool:
        # Implement your logic
        pass

    def validate_options(self, options: dict) -> bool:
        # Validate configuration options
        pass
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## Support

For issues, questions, or suggestions, please open an issue on the project repository.
