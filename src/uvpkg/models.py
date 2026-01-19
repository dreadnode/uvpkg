"""Data models for uvpkg packages and manifests."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DependencySource(str, Enum):
    """Source type for package dependencies."""

    REGISTRY = "registry"
    PATH = "path"
    GIT = "git"


class PackageDependency(BaseModel):
    """A package dependency with support for multiple source types."""

    # Registry source
    version: str | None = None

    # Path source (local)
    path: str | None = None

    # Git source
    git: str | None = None
    ref: str | None = None  # branch, tag, or commit
    subdir: str | None = None  # subdirectory within repo

    # Common options
    include: list[str] | None = None  # partial install patterns
    dev: bool = False  # dev-only dependency

    @property
    def source(self) -> DependencySource:
        """Determine the dependency source type."""
        if self.path:
            return DependencySource.PATH
        if self.git:
            return DependencySource.GIT
        return DependencySource.REGISTRY

    def resolve_path(self, base: Path) -> Path | None:
        """Resolve path dependency relative to base directory."""
        if self.path:
            p = Path(self.path)
            return p if p.is_absolute() else base / p
        return None


class PackageRepository(BaseModel):
    """Repository information for a package."""

    type: str = "git"
    url: str
    directory: str | None = None


class PackageManifest(BaseModel):
    """
    The openpackage.yml manifest file schema.

    Defines package metadata and dependencies.
    """

    name: str
    version: str = "0.1.0"
    description: str | None = None
    author: str | None = None
    license: str | None = None
    homepage: str | None = None
    keywords: list[str] = Field(default_factory=list)
    repository: PackageRepository | None = None

    # Package is not publishable to registry
    private: bool = False

    # Package contains subset of files (for workspace manifests)
    partial: bool = False

    # Dependencies
    packages: dict[str, PackageDependency | str] = Field(default_factory=dict)
    dev_packages: dict[str, PackageDependency | str] = Field(
        default_factory=dict, alias="dev-packages"
    )

    class Config:
        populate_by_name = True

    def get_dependency(self, name: str) -> PackageDependency | None:
        """Get a dependency by name, normalizing string versions."""
        dep = self.packages.get(name) or self.dev_packages.get(name)
        if dep is None:
            return None
        if isinstance(dep, str):
            return PackageDependency(version=dep)
        return dep

    def all_dependencies(self, include_dev: bool = False) -> dict[str, PackageDependency]:
        """Get all dependencies as PackageDependency objects."""
        result: dict[str, PackageDependency] = {}

        for name, dep in self.packages.items():
            if isinstance(dep, str):
                result[name] = PackageDependency(version=dep)
            else:
                result[name] = dep

        if include_dev:
            for name, dep in self.dev_packages.items():
                if isinstance(dep, str):
                    result[name] = PackageDependency(version=dep, dev=True)
                else:
                    dep.dev = True
                    result[name] = dep

        return result


class PackageFile(BaseModel):
    """A file within a package."""

    path: str  # relative path within package
    content: str
    encoding: str = "utf-8"

    @property
    def is_config(self) -> bool:
        """Check if this is a configuration file."""
        return self.path.endswith((".yml", ".yaml", ".json", ".toml"))

    @property
    def is_markdown(self) -> bool:
        """Check if this is a markdown file."""
        return self.path.endswith(".md")


class Package(BaseModel):
    """A complete package with metadata and files."""

    manifest: PackageManifest
    files: list[PackageFile] = Field(default_factory=list)
    source_path: Path | None = None  # where package was loaded from

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    def get_file(self, path: str) -> PackageFile | None:
        """Get a file by path."""
        for f in self.files:
            if f.path == path:
                return f
        return None

    def file_paths(self) -> list[str]:
        """Get all file paths in the package."""
        return [f.path for f in self.files]


class MergeStrategy(str, Enum):
    """Strategy for merging files during installation."""

    REPLACE = "replace"  # overwrite target completely
    DEEP = "deep"  # deep merge preserving nested structures
    SHALLOW = "shallow"  # shallow merge (top-level only)
    COMPOSITE = "composite"  # compose with delimiters (for markdown)
    SKIP = "skip"  # skip if target exists


class ConflictStrategy(str, Enum):
    """Strategy for handling file conflicts."""

    PROMPT = "prompt"  # ask user
    OVERWRITE = "overwrite"  # always overwrite
    SKIP = "skip"  # never overwrite
    BACKUP = "backup"  # create backup before overwrite


class Flow(BaseModel):
    """
    File transformation flow from source to target.

    Supports glob patterns, JSONPath extraction, and merge strategies.
    """

    from_pattern: str = Field(alias="from")  # source pattern
    to: str | dict[str, Any]  # target path or multi-target config

    # Transformation options
    pick: list[str] | None = None  # whitelist keys
    omit: list[str] | None = None  # blacklist keys
    path: str | None = None  # JSONPath extraction
    embed: str | None = None  # nest under key
    merge: MergeStrategy = MergeStrategy.REPLACE

    class Config:
        populate_by_name = True


class InstallOptions(BaseModel):
    """Options for package installation."""

    dry_run: bool = False
    force: bool = False
    dev: bool = False  # include dev dependencies
    platforms: list[str] | None = None  # specific platforms only
    conflict: ConflictStrategy = ConflictStrategy.PROMPT
    variables: dict[str, str] = Field(default_factory=dict)


class PackageStatus(BaseModel):
    """Status of an installed package."""

    name: str
    installed_version: str | None = None
    available_version: str | None = None
    source: DependencySource
    source_path: str | None = None  # path/git url
    is_dev: bool = False
    files: list[str] = Field(default_factory=list)  # installed file paths
