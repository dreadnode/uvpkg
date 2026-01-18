"""
uvpkg - Universal AI coding package manager.

A Python/UV reimplementation of openpackage for managing AI coding configurations
across multiple platforms (Claude Code, Cursor, Windsurf, etc.).
"""

from uvpkg.models import (
    Package,
    PackageFile,
    PackageManifest,
    PackageDependency,
)
from uvpkg.platforms import Platform, get_platform, list_platforms
from uvpkg.manager import PackageManager
from uvpkg.installer import Installer

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Models
    "Package",
    "PackageFile",
    "PackageManifest",
    "PackageDependency",
    # Platforms
    "Platform",
    "get_platform",
    "list_platforms",
    # Core
    "PackageManager",
    "Installer",
]
