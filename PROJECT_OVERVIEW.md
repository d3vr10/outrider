# Outrider Project Overview

## What is Outrider?

Outrider is an extensible automation tool for deploying OCI (Docker) images to air-gapped and remote systems. It's specifically designed to solve the problem of delivering container images from online systems to isolated Kubernetes clusters and other remote environments that don't have internet access.

## Key Features

✓ **Abstracted Architecture** - Easily swap container runtimes, transport protocols, and deployment methods
✓ **Plugin System** - Extensible post-deployment actions for different use cases
✓ **Configuration-Driven** - Simple YAML configuration for repeatable deployments
✓ **Batch Operations** - Deploy to multiple systems in a single command
✓ **Well-Documented** - Comprehensive documentation and examples included
✓ **Minimal Dependencies** - Only requires paramiko, pyyaml, and click

## Problem It Solves

**Scenario**: You have a Kubernetes cluster in an air-gapped network (no internet access) and need to deploy container images to it.

**Manual Process**:
1. Pull images on a machine with internet
2. Save images to tar files
3. Manually copy files via USB or network
4. SSH to each cluster node
5. Import images into container runtime
6. Repeat for every image update

**With Outrider**:
```bash
outrider deploy -c config.yaml
```

That's it. Everything else is automated.

## Project Structure

```
outrider/
├── outrider/                 # Main Python package
│   ├── cli.py              # Command-line interface (entry point)
│   │
│   ├── core/               # Core orchestration
│   │   ├── config.py       # YAML configuration loading
│   │   └── orchestrator.py # Main workflow coordination
│   │
│   ├── runtime/            # Container runtime abstraction
│   │   ├── base.py         # Abstract base class
│   │   └── docker.py       # Docker implementation
│   │
│   ├── transport/          # Network transport abstraction
│   │   ├── base.py         # Abstract base class
│   │   └── ssh.py          # SSH/SCP implementation
│   │
│   └── plugins/            # Post-deployment plugins
│       ├── base.py         # Abstract base class
│       ├── k3s_airgap.py   # K3s cluster import
│       └── generic_ssh.py  # Arbitrary SSH commands
│
├── examples/               # Example configurations
│   ├── basic-k3s-deployment.yaml
│   ├── docker-swarm-deployment.yaml
│   └── file-transfer-only.yaml
│
├── setup.py               # Package setup
├── requirements.txt       # Python dependencies
│
└── Documentation
    ├── README.md          # Full documentation
    ├── QUICKSTART.md      # Quick start guide (5 minutes)
    ├── USAGE_EXAMPLES.md  # Practical examples
    ├── ARCHITECTURE.md    # How to extend the tool
    └── PROJECT_OVERVIEW.md (this file)
```

## How It Works

### 1. Configuration
User creates a YAML file specifying:
- Images to pull
- Target systems to deploy to
- How to deploy images (plugin selection)

### 2. Execution Flow
```
Load Config → Validate → Pull Images → Compress → Transfer → Execute Plugin → Done
```

### 3. On Each Target
```
Transfer TAR → Run Post-Instructions (optional) → Cleanup (optional)
```

## Quick Example

**Configuration (config.yaml)**:
```yaml
images:
  - nginx:latest
  - redis:7-alpine

targets:
  - host: 192.168.1.10
    user: ubuntu

post_instructions:
  plugin: k3s_airgap
  options:
    cleanup_tar: true
```

**Deployment**:
```bash
outrider deploy -c config.yaml
```

**What happens**:
1. Docker pulls `nginx:latest` and `redis:7-alpine`
2. Both images are saved to `images.tar`
3. `images.tar` is transferred to `192.168.1.10` via SSH
4. Images are automatically imported into K3s containerd
5. `images.tar` is deleted from the remote system

## Extensibility

Outrider is designed to be extended. Examples:

### Add Podman Support
Implement `PodmanRuntime` extending `BaseRuntime` and register in config

### Add SFTP Transport
Implement `SFTPTransport` extending `BaseTransport` and register in config

### Add Custom Deployment
Implement custom plugin extending the plugin interface

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed extension guide.

## Use Cases

| Use Case | Configuration |
|----------|---------------|
| Air-gapped K3s cluster | K3s air-gap plugin |
| Docker Swarm deployment | Generic SSH with docker load |
| Kubernetes with docker-in-docker | Generic SSH with docker load |
| File transfer only | No post-instructions |
| Corporate image registry proxy | Multiple targets with same images |

## Command Reference

```bash
# Install
pip install -e .

# Validate configuration
outrider validate -c config.yaml

# Deploy with normal logging
outrider deploy -c config.yaml

# Deploy with verbose logging
outrider deploy -c config.yaml -v

# Get help
outrider --help
outrider deploy --help
```

## Documentation Map

| Document | Purpose | For Whom |
|----------|---------|----------|
| [QUICKSTART.md](QUICKSTART.md) | Get started in 5 minutes | New users |
| [README.md](README.md) | Complete feature documentation | All users |
| [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) | Practical real-world examples | Users with specific scenarios |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Design and extension guide | Developers extending Outrider |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | This document | Getting oriented |

## Core Concepts

### Abstractions

Outrider uses abstraction layers for extensibility:

1. **Runtime** - Abstract interface for pulling and saving images
   - Implemented: Docker
   - Extensible to: Podman, containerd, etc.

2. **Transport** - Abstract interface for file transfer and remote execution
   - Implemented: SSH/SFTP
   - Extensible to: HTTP, S3, NFS, etc.

3. **Plugins** - Abstract interface for post-deployment actions
   - Implemented: K3s, Generic SSH
   - Extensible to: Kubernetes, Docker Swarm, custom scripts, etc.

### Configuration-Driven Design

All behavior is controlled via YAML configuration, not code. This means:
- No recompilation needed for different deployments
- Easy versioning of deployment configurations
- Separation of concerns (config vs. code)

### Sequential Processing

Operations happen in sequence:
1. All images pulled
2. All images compressed into one tar file
3. Tar transferred to target #1, deployed
4. Tar transferred to target #2, deployed
5. Tar transferred to target #3, deployed
... and so on

This is simple and reliable. Parallelization can be added in future versions.

## Why Outrider?

The name "Outrider" comes from two meanings:
1. **Outrider** (definition): A person who rides ahead of a group to scout
2. **Out-rider**: Riding containers out to remote/isolated systems

## Technology Stack

- **Language**: Python 3.8+
- **SSH Library**: paramiko
- **YAML Library**: pyyaml
- **CLI Framework**: click
- **No heavy dependencies**: Can run on minimal systems

## Performance Characteristics

| Operation | Complexity |
|-----------|------------|
| Pull images | O(n) where n = number of images |
| Compress images | O(s) where s = total image size |
| Transfer to one target | O(s) where s = tar file size |
| Execute plugin | O(1) per target |
| Overall | O(n + s + (t × s)) where t = number of targets |

For typical use cases:
- Pull images: Minutes (depends on registry and network)
- Compress: Minutes (depends on image sizes)
- Transfer: Minutes (depends on tar size and network speed)
- Plugins: Seconds (depends on plugin implementation)

## Logging

Outrider provides detailed logging:

**Normal mode**:
```
INFO - Pulling image: nginx:latest
INFO - Successfully pulled: nginx:latest
INFO - Saving images to images.tar
INFO - Successfully created tar file: images.tar (150.23 MB)
INFO - Transferring to ubuntu@192.168.1.10:22
INFO - Successfully transferred images.tar
INFO - Executing post-instructions on 192.168.1.10
INFO - Successfully imported images to K3s
```

**Verbose mode** (`-v` flag):
- DEBUG level logging with detailed operation info
- Useful for troubleshooting
- Shows subprocess output and SSH details

## Security Considerations

- SSH keys stored in standard location (~/.ssh/id_rsa)
- SSH connections use standard encryption
- No credentials stored in configuration files
- SFTP for secure file transfer
- All remote commands logged (in verbose mode)

## Limitations and Future Work

**Current Limitations**:
- Sequential operations (not parallel)
- Docker/SSH only (though easy to extend)
- No progress bar or ETA
- No image signing/verification
- No scheduling or automation hooks

**Future Enhancements**:
- Parallel transfers for faster deployment
- Progress bars and transfer speed info
- Image signature verification
- Retry logic with exponential backoff
- Web UI for configuration management
- Integration with CI/CD systems
- Prometheus metrics export
- Webhook support for notifications

## Getting Started

1. **Read**: [QUICKSTART.md](QUICKSTART.md) (5 minutes)
2. **Install**: `pip install -e .`
3. **Configure**: Copy [config.example.yaml](config.example.yaml) and customize
4. **Validate**: `outrider validate -c config.yaml`
5. **Deploy**: `outrider deploy -c config.yaml`

## Contributing

To extend Outrider:

1. **Add Runtime**: Extend `BaseRuntime` in `outrider/runtime/`
2. **Add Transport**: Extend `BaseTransport` in `outrider/transport/`
3. **Add Plugin**: Implement plugin interface in `outrider/plugins/`
4. **Test**: Validate with `outrider validate -c test-config.yaml`
5. **Document**: Update examples and add to ARCHITECTURE.md

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed examples.

## Support and Issues

For questions or issues:
1. Check [QUICKSTART.md](QUICKSTART.md)
2. Read [README.md](README.md)
3. Review [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)
4. Check [ARCHITECTURE.md](ARCHITECTURE.md) for extension questions
5. File an issue with detailed error messages and verbose logs

## License

MIT License - See LICENSE file (if included)

---

**Next Steps:**
- Read [QUICKSTART.md](QUICKSTART.md) to get started
- See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for your specific use case
- Check [ARCHITECTURE.md](ARCHITECTURE.md) if you want to extend Outrider
