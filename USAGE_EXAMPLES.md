# Outrider Usage Examples

This document provides practical examples for common use cases.

## Table of Contents
1. [Air-gapped K3s Cluster](#air-gapped-k3s-cluster)
2. [Docker Hosts](#docker-hosts)
3. [Docker Swarm](#docker-swarm)
4. [File Transfer Only](#file-transfer-only)
5. [Multiple Clusters](#multiple-clusters)
6. [Custom Deployment](#custom-deployment)

## Air-gapped K3s Cluster

Deploy images to an isolated K3s cluster without internet access.

**Configuration:**

```yaml
images:
  - k3s.io/rancher/k3s-payload:v1.28.0
  - coredns:1.10.1
  - rancher/local-path-provisioner:v0.0.24

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  - host: airgap-k3s-master
    user: ubuntu
    port: 22

  - host: airgap-k3s-worker-1
    user: ubuntu
    port: 22

  - host: airgap-k3s-worker-2
    user: ubuntu
    port: 22

output_tar: ./k3s-images.tar
remote_tar_path: /tmp/k3s-images.tar

post_instructions:
  plugin: k3s_airgap
  options:
    k3s_path: /usr/local/bin/k3s
    containerd_path: /run/k3s/containerd/containerd.sock
    cleanup_tar: true
```

**Usage:**

```bash
# Create config file
cat > k3s-config.yaml << 'EOF'
# (paste configuration above)
EOF

# Validate configuration
outrider validate -c k3s-config.yaml

# Deploy images
outrider deploy -c k3s-config.yaml

# Verify images are available
kubectl get images  # or similar command for your cluster
```

**What happens:**
1. Docker pulls k3s images to the online machine
2. Images are saved to a tar file (k3s-images.tar)
3. Tar file is transferred to each K3s node via SSH
4. Images are imported into containerd on each node
5. Tar files are cleaned up automatically

---

## Docker Hosts

Deploy images to standalone Docker hosts using the Docker plugin.

**Configuration:**

```yaml
images:
  - myapp:v1.0
  - postgres:15-alpine
  - redis:7-alpine

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  - host: docker-host-1.example.com
    user: ubuntu
    port: 22

  - host: docker-host-2.example.com
    user: ubuntu
    port: 22

output_tar: ./docker-images.tar
remote_tar_path: /tmp/docker-images.tar

post_instructions:
  plugin: docker
  options:
    docker_cmd: docker
    cleanup_tar: true
    use_sudo: false
```

**Usage:**

```bash
# Deploy to Docker hosts
outrider deploy -c docker-config.yaml -v

# Verify images loaded on remote host
ssh ubuntu@docker-host-1.example.com docker images
```

**What happens:**
1. Docker pulls images on the online machine
2. Images are saved to a tar file (docker-images.tar)
3. Tar file is transferred to each Docker host via SSH
4. Images are loaded into Docker daemon on each host
5. Tar files are cleaned up automatically

**Note**: If the Docker daemon requires sudo, set `use_sudo: true` in the options.

---

## Docker Swarm

Deploy container images to Docker Swarm cluster nodes.

**Configuration:**

```yaml
images:
  - mycompany/webapp:v2.1.0
  - mycompany/api:v2.1.0
  - mycompany/worker:v2.1.0
  - postgres:15-alpine
  - redis:7-alpine

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  - host: swarm-manager-1
    user: ubuntu
    port: 22

  - host: swarm-node-1
    user: ubuntu
    port: 22

  - host: swarm-node-2
    user: ubuntu
    port: 22

output_tar: ./swarm-images.tar
remote_tar_path: /opt/docker-images.tar

post_instructions:
  plugin: generic_ssh
  options:
    command: |
      docker load < {tar_path} && \
      rm -f {tar_path} && \
      docker images | grep mycompany
```

**Usage:**

```bash
# Create and deploy
outrider deploy -c swarm-config.yaml -v

# SSH to node and verify
ssh ubuntu@swarm-node-1 docker images
```

**Alternative with Docker Plugin:**

Instead of generic_ssh, you can also use the Docker plugin for simpler configuration:

```yaml
post_instructions:
  plugin: docker
  options:
    docker_cmd: docker
    cleanup_tar: true
```

The Docker plugin is recommended for standard Docker deployments, while generic_ssh is more flexible for custom workflows.

---

## File Transfer Only

Transfer images to remote systems for manual deployment.

**Configuration:**

```yaml
images:
  - ubuntu:22.04
  - centos:7
  - golang:1.21
  - node:20-alpine
  - python:3.12-slim

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/build-key.pem

targets:
  - host: backup.example.com
    user: backup
    port: 2222

output_tar: ./backup-images.tar
remote_tar_path: /backup/docker/images.tar

# No post-instructions - just transfer files
```

**Usage:**

```bash
# Transfer files
outrider deploy -c backup-config.yaml

# SSH to system and manually load images later
ssh backup@backup.example.com
docker load < /backup/docker/images.tar
```

---

## Multiple Clusters

Deploy the same images to multiple Kubernetes clusters.

**Configuration:**

```yaml
images:
  - metrics-server:v0.6.3
  - cert-manager:v1.13.0
  - ingress-nginx-controller:v1.8.1

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  # Production cluster
  - host: prod-k3s-master
    user: ubuntu
    port: 22

  - host: prod-k3s-worker-1
    user: ubuntu
    port: 22

  - host: prod-k3s-worker-2
    user: ubuntu
    port: 22

  # Staging cluster
  - host: staging-k3s-master
    user: ubuntu
    port: 22

  - host: staging-k3s-worker-1
    user: ubuntu
    port: 22

  # Development cluster
  - host: dev-k3s-master
    user: ubuntu
    port: 22

output_tar: ./infrastructure-images.tar
remote_tar_path: /tmp/k3s-images.tar

post_instructions:
  plugin: k3s_airgap
  options:
    k3s_path: /usr/local/bin/k3s
    containerd_path: /run/k3s/containerd/containerd.sock
    cleanup_tar: true
```

**Usage:**

```bash
# Deploy to all clusters
outrider deploy -c multi-cluster.yaml -v

# Monitor progress - tool will show transfer to each node
```

---

## Custom Deployment

Execute custom scripts on remote systems.

**Configuration:**

```yaml
images:
  - mycompany/app:latest

runtime:
  type: docker

transport:
  type: ssh
  options:
    key_file: ~/.ssh/id_rsa

targets:
  - host: deployment-server
    user: deploy
    port: 22

output_tar: ./app-images.tar
remote_tar_path: /home/deploy/images.tar

post_instructions:
  plugin: generic_ssh
  options:
    command: |
      set -e
      cd /home/deploy
      docker load < images.tar
      docker-compose up -d
      rm -f images.tar
      echo "Deployment complete at $(date)"
```

**Usage:**

```bash
# Deploy with custom post-deployment script
outrider deploy -c custom-deploy.yaml

# Check if deployment succeeded
ssh deploy@deployment-server docker ps
```

---

## Advanced: Multi-step Deployment

For complex deployments, you can chain multiple outrider runs:

```bash
#!/bin/bash

# Step 1: Deploy to staging
outrider deploy -c staging-config.yaml || exit 1

# Step 2: Run tests
./tests/smoke-tests.sh staging || exit 1

# Step 3: Deploy to production
outrider deploy -c prod-config.yaml || exit 1

echo "Deployment pipeline complete!"
```

---

## Common Tasks

### List available images

```bash
# Check which images will be pulled
grep "^  - " config.yaml
```

### Test SSH connectivity before deployment

```bash
# Test connection to each target
for host in $(grep "host:" config.yaml | awk '{print $2}'); do
    echo "Testing $host..."
    ssh -i ~/.ssh/id_rsa ubuntu@$host "docker --version" && echo "✓ OK" || echo "✗ FAILED"
done
```

### Monitor transfer progress

```bash
# Use verbose mode to see detailed progress
outrider deploy -c config.yaml -v | grep -i transfer
```

### Verify images on remote system

```bash
# SSH to remote and check images
ssh ubuntu@target-host docker images | grep "REPOSITORY\|myimage"
```

### Clean up old images locally

```bash
# After successful deployment, remove local tar file
rm -f ./images.tar

# Or let cleanup_tar handle remote cleanup automatically
```

---

## Troubleshooting Examples

### SSH Key Permission Error

```
Error: Failed to connect to host: SSH key permission error
```

**Solution:**

```bash
# Fix SSH key permissions
chmod 600 ~/.ssh/id_rsa
chmod 700 ~/.ssh

# Verify connectivity
ssh -i ~/.ssh/id_rsa ubuntu@target-host whoami
```

### Docker Pull Timeout

```
Error: Pull timeout for myimage:latest
```

**Solution:**

```bash
# Test docker pull manually
docker pull myimage:latest

# Check docker daemon
docker info

# Increase timeout by retrying
outrider deploy -c config.yaml -v
```

### K3s Socket Not Found

```
Error: Failed to import images: /run/k3s/containerd/containerd.sock not found
```

**Solution:**

```bash
# SSH to K3s node and check socket
ssh ubuntu@k3s-node ls -l /run/k3s/containerd/containerd.sock

# Verify K3s is running
ssh ubuntu@k3s-node sudo k3s kubectl get nodes

# Update config with correct path
# Check: ls -la /run/k3s/containerd/ on the remote node
```

---

## Performance Tips

### For large images
1. Use SSD storage for temporary tar files
2. Increase SSH cipher speed if transferring over slow network
3. Consider splitting large deployments into separate outrider runs

### For many targets
1. SSH transfers happen sequentially - each target gets the file one at a time
2. For parallel transfers, run multiple outrider instances with different target lists

### For air-gapped environments
1. Pre-stage the tar file on a USB drive or network share
2. Use `file-transfer-only` mode and then manually import images
3. Cache the tar file and reuse for multiple deployments

---

## Integration Examples

### With CI/CD (GitHub Actions)

```yaml
name: Deploy Images

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install outrider
        run: |
          cd outrider
          pip install -e .

      - name: Deploy to staging
        run: |
          outrider deploy -c configs/staging.yaml
        env:
          SSH_KEY: ${{ secrets.STAGING_SSH_KEY }}
```

### With Ansible

```yaml
- name: Deploy container images with Outrider
  hosts: localhost
  tasks:
    - name: Run outrider deploy
      command: outrider deploy -c "{{ config_file }}"
      register: deploy_result

    - name: Display deployment result
      debug:
        msg: "{{ deploy_result.stdout }}"
```

### With Terraform

```hcl
resource "null_resource" "outrider_deploy" {
  provisioner "local-exec" {
    command = "outrider deploy -c ${var.config_file}"
  }

  depends_on = [
    module.k3s_cluster
  ]
}
```

---

For more information, see the main [README.md](README.md) or run:

```bash
outrider --help
outrider deploy --help
outrider validate --help
```
