"""Post-instruction plugins for deployment"""

from .k3s_airgap import K3sAirgapPlugin
from .generic_ssh import GenericSSHPlugin
from .docker import DockerPlugin

__all__ = ["K3sAirgapPlugin", "GenericSSHPlugin", "DockerPlugin"]
