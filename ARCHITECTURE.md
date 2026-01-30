# Outrider Architecture

This document describes the architecture of Outrider and how to extend it with custom implementations.

## Design Principles

1. **Abstraction**: Core functionality is abstracted to interfaces, allowing multiple implementations
2. **Plugin System**: Post-deployment actions are implemented as plugins for maximum flexibility
3. **Configuration-Driven**: All behavior is controlled via YAML configuration
4. **Sequential Processing**: Operations happen one target at a time (parallelization possible in future)
5. **Minimal Dependencies**: Only essential libraries (paramiko, pyyaml, click)

## Component Architecture

```
┌─────────────────────────────────────────┐
│            CLI Interface                 │
│         (outrider/cli.py)               │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│          Configuration                   │
│         (core/config.py)                │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│          Orchestrator                    │
│       (core/orchestrator.py)            │
│                                          │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ Pull Images  │  │Compress TAR  │    │
│  │   (Runtime)  │  │   (Runtime)  │    │
│  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ Transfer TAR │  │Execute Plugin│    │
│  │(Transport)   │  │(Plugins)     │    │
│  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────┘
        │                    │
        │                    │
   ┌────▼──────┐      ┌──────▼─────┐
   │  Runtime  │      │  Transport  │
   │           │      │             │
   │ ┌───────┐ │      │  ┌────────┐ │
   │ │Docker │ │      │  │  SSH   │ │
   │ │Podman?│ │      │  │ Others?│ │
   │ └───────┘ │      │  └────────┘ │
   └───────────┘      └─────────────┘
        │                    │
        │                    │
   ┌────▼──────┐      ┌──────▼─────┐
   │  Plugins  │
   │           │
   │ ┌────────┐│
   │ │  K3s   ││
   │ │Generic ││
   │ │Custom? ││
   │ └────────┘│
   └───────────┘
```

## Core Classes and Interfaces

### Runtime Abstraction

**File**: `outrider/runtime/base.py`

```python
class BaseRuntime(ABC):
    @abstractmethod
    def pull_image(self, image_name: str) -> bool:
        """Pull image from registry"""
        pass

    @abstractmethod
    def save_images(self, image_list: List[str], output_tar: str) -> bool:
        """Save images to tar file"""
        pass

    @abstractmethod
    def load_images(self, tar_file: str) -> bool:
        """Load images from tar file"""
        pass
```

**Current Implementation**: `DockerRuntime`
- Uses Docker CLI commands
- Supports custom docker command path
- Handles errors and timeouts

### Transport Abstraction

**File**: `outrider/transport/base.py`

```python
class BaseTransport(ABC):
    @abstractmethod
    def transfer_file(self, local_path: str, remote_host: RemoteHost,
                     remote_path: str) -> bool:
        """Transfer file to remote system"""
        pass

    @abstractmethod
    def execute_remote(self, remote_host: RemoteHost, command: str) -> \
            Tuple[int, str, str]:
        """Execute command on remote system"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connections"""
        pass
```

**Current Implementation**: `SSHTransport`
- Uses paramiko SSH library
- Supports key-based and password authentication
- Caches connections per host
- SFTP for file transfer

### Plugin System

**File**: `outrider/plugins/base.py`

```python
class BasePlugin(ABC):
    @abstractmethod
    def execute(self, remote_host: RemoteHost, tar_path: str,
               options: Dict[str, Any]) -> bool:
        """Execute post-deployment actions"""
        pass

    @abstractmethod
    def validate_options(self, options: Dict[str, Any]) -> bool:
        """Validate configuration options"""
        pass
```

**Current Implementations**:
- `K3sAirgapPlugin`: Imports images into K3s containerd
- `GenericSSHPlugin`: Executes arbitrary SSH commands

### Configuration

**File**: `outrider/core/config.py`

```python
class Config:
    @property
    def images(self) -> List[str]:
        """Get list of images to pull"""

    @property
    def runtime_config(self) -> Dict[str, Any]:
        """Get runtime configuration"""

    @property
    def transport_config(self) -> Dict[str, Any]:
        """Get transport configuration"""

    @property
    def targets(self) -> List[RemoteHost]:
        """Get remote targets"""

    @property
    def post_instructions(self) -> Optional[Dict[str, Any]]:
        """Get post-instruction configuration"""
```

### Orchestrator

**File**: `outrider/core/orchestrator.py`

Coordinates the entire workflow:
1. Initialize runtime
2. Initialize transport
3. Pull images
4. Compress images
5. Transfer to each target
6. Execute post-instructions
7. Cleanup

## Workflow

```
Load Config
    │
    ├─▶ Initialize Runtime
    │     └─▶ Verify Docker/Podman available
    │
    ├─▶ Initialize Transport
    │     └─▶ Test SSH connectivity (lazy)
    │
    ├─▶ Pull Images
    │     └─▶ For each image: docker pull
    │
    ├─▶ Compress Images
    │     └─▶ docker save -o images.tar
    │
    ├─▶ For each Target:
    │     ├─▶ Transfer TAR via SFTP
    │     └─▶ If post_instructions:
    │           └─▶ Execute plugin.execute()
    │               └─▶ K3s plugin: ctr image import
    │               └─▶ SSH plugin: custom command
    │
    └─▶ Cleanup & Report
```

## Extending Outrider

### Adding a New Container Runtime

**Example: Add Podman support**

1. Create `outrider/runtime/podman.py`:

```python
from .base import BaseRuntime

class PodmanRuntime(BaseRuntime):
    def __init__(self, podman_cmd: str = "podman"):
        self.podman_cmd = podman_cmd
        self._verify_podman()

    def _verify_podman(self) -> None:
        subprocess.run([self.podman_cmd, "version"], check=True)

    def pull_image(self, image_name: str) -> bool:
        result = subprocess.run(
            [self.podman_cmd, "pull", image_name],
            capture_output=True,
            check=False
        )
        return result.returncode == 0

    def save_images(self, image_list: List[str], output_tar: str) -> bool:
        cmd = [self.podman_cmd, "save", "-o", output_tar] + image_list
        result = subprocess.run(cmd, capture_output=True, check=False)
        return result.returncode == 0

    def load_images(self, tar_file: str) -> bool:
        with open(tar_file, "rb") as f:
            result = subprocess.run(
                [self.podman_cmd, "load"],
                stdin=f,
                capture_output=True,
                check=False
            )
        return result.returncode == 0
```

2. Update `outrider/runtime/__init__.py`:

```python
from .podman import PodmanRuntime

__all__ = ["DockerRuntime", "PodmanRuntime"]
```

3. Update `outrider/core/orchestrator.py` to handle podman:

```python
def _init_runtime(self) -> bool:
    runtime_type = self.config.runtime_config.get("type", "docker")

    if runtime_type == "docker":
        self.runtime = DockerRuntime(...)
    elif runtime_type == "podman":
        self.runtime = PodmanRuntime(...)
    # ... etc
```

### Adding a New Transport Protocol

**Example: Add HTTP transport for file transfer**

1. Create `outrider/transport/http.py`:

```python
from .base import BaseTransport, RemoteHost
import requests

class HTTPTransport(BaseTransport):
    def __init__(self, upload_endpoint: str):
        self.upload_endpoint = upload_endpoint

    def transfer_file(self, local_path: str, remote_host: RemoteHost,
                     remote_path: str) -> bool:
        with open(local_path, "rb") as f:
            files = {"file": f}
            data = {"path": remote_path, "host": remote_host.host}
            response = requests.post(self.upload_endpoint, files=files, data=data)
        return response.status_code == 200

    def execute_remote(self, remote_host: RemoteHost, command: str) -> \
            Tuple[int, str, str]:
        data = {"host": remote_host.host, "command": command}
        response = requests.post(f"{self.upload_endpoint}/exec", json=data)
        result = response.json()
        return result["return_code"], result["stdout"], result["stderr"]

    def close(self) -> None:
        pass
```

### Adding a New Plugin

**Example: Add Kubernetes native plugin**

1. Create `outrider/plugins/k8s_native.py`:

```python
import logging
from typing import Dict, Any
from outrider.transport.base import RemoteHost, BaseTransport

logger = logging.getLogger(__name__)

class K8sNativePlugin:
    def __init__(self, transport: BaseTransport):
        self.transport = transport

    def execute(self, remote_host: RemoteHost, tar_path: str,
               options: Dict[str, Any]) -> bool:
        """Load images into K8s node"""

        # Copy tar to /var/lib/docker on node
        cmd = f"docker load < {tar_path} && rm {tar_path}"

        return_code, _, stderr = self.transport.execute_remote(
            remote_host, cmd
        )

        if return_code != 0:
            logger.error(f"Failed to load images: {stderr}")
            return False

        return True

    def validate_options(self, options: Dict[str, Any]) -> bool:
        return True
```

2. Update `outrider/plugins/__init__.py`:

```python
from .k8s_native import K8sNativePlugin

__all__ = ["K3sAirgapPlugin", "GenericSSHPlugin", "K8sNativePlugin"]
```

3. Update `outrider/core/orchestrator.py`:

```python
if plugin_type == "k8s_native":
    plugin = K8sNativePlugin(self.transport)
```

4. Use in configuration:

```yaml
post_instructions:
  plugin: k8s_native
  options: {}
```

## Configuration Extension Points

### Runtime Options

```yaml
runtime:
  type: docker
  options:
    cmd: /usr/bin/docker  # Custom docker path
    # Future: registry_url, auth_config, etc.
```

### Transport Options

```yaml
transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa
    # Future: proxy_host, known_hosts_file, etc.
```

### Plugin Options

Each plugin defines its own options in the configuration:

```yaml
post_instructions:
  plugin: custom_plugin
  options:
    # Plugin-specific options
```

## Data Flow

```
Configuration (YAML)
    │
    ├─▶ Images List
    │     └─▶ runtime.pull_image()
    │         └─▶ saved to output_tar
    │
    ├─▶ Transport Config
    │     └─▶ transport.transfer_file()
    │         └─▶ to remote_tar_path
    │
    ├─▶ Targets List
    │     └─▶ For each target:
    │         ├─▶ transfer_file()
    │         └─▶ plugin.execute()
    │
    └─▶ Post-Instructions Config
          └─▶ plugin.validate_options()
              └─▶ plugin.execute()
```

## Error Handling

Each component has error handling:

- **Runtime**: Timeouts, missing images, docker daemon unavailable
- **Transport**: SSH connection failures, authentication errors, file transfer failures
- **Plugins**: Command execution failures, validation errors
- **Orchestrator**: Validates config, handles component failures, logs all steps

## Logging

Logging is configured at the CLI level with support for verbose mode:

```bash
outrider deploy -c config.yaml -v  # Debug level
outrider deploy -c config.yaml     # Info level
```

All components use Python's logging module:

```python
logger = logging.getLogger(__name__)
logger.info("User-facing message")
logger.debug("Technical detail")
logger.error("Error message")
```

## Performance Considerations

1. **Sequential Transfers**: Transfers happen one target at a time
   - Pro: Simpler logic, controlled resource usage
   - Con: Slower for many targets
   - Future: Could add parallel transfer pool

2. **Connection Caching**: SSH connections are cached per host
   - Reduces connection overhead
   - Connections closed on shutdown

3. **Streaming**: Large files streamed via SFTP
   - Memory efficient
   - Suitable for large images

## Future Extensions

Possible future enhancements:

1. **Parallel Operations**: Transfer to multiple targets concurrently
2. **Progress Reporting**: Show transfer progress via progress bar
3. **Retry Logic**: Automatic retry on failure
4. **Image Registry Cache**: Keep local cache of pulled images
5. **Cloud Transports**: S3, Azure Blob, GCS
6. **Image Signing**: Verify image signatures before deployment
7. **Scheduling**: Cron-like scheduling of deployments
8. **Web UI**: Dashboard for managing deployments
9. **Metrics**: Prometheus-compatible metrics export
10. **Multi-cloud**: Support for multiple cloud providers

---

For implementation examples, see [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)
