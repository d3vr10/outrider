"""Post-instruction plugins for deployment"""

from .k3s_airgap import K3sAirgapPlugin
from .generic_ssh import GenericSSHPlugin

__all__ = ["K3sAirgapPlugin", "GenericSSHPlugin"]
