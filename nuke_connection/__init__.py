"""
Nuke 17.0 Connection Module
============================
Provides socket-based and module-based connectivity to Foundry Nuke 17.0.
Supports sending Python commands, receiving results, and managing sessions.
"""

from .connector import NukeConnector
from .session import NukeSession

__all__ = ["NukeConnector", "NukeSession"]
__version__ = "1.0.0"
