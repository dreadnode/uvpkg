"""
Package manager for loading, saving, and discovering packages.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterator

import yaml

from uvpkg.models import (
    DependencySource,
    Package,
    PackageDependency,
    PackageFile,
    PackageManifest,
    PackageStatus,
)

# Files to ignore when discovering package contents
JUNK_PATTERNS = [
    ".git",
    ".gitignore",
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    ".venv",
    "node_modules",
    ".uvpkg",
    "uvpkg.lock",
]

MANIFEST_FILENAMES = ["uvpkg.yml", "uvpkg.yaml", "openpackage.yml", "openpackage.yaml"]


def is_junk(path: Path) -> bool:
    """Check if a path should be ignored."""
    name = path.name
    for pattern in JUNK_PATTERNS:
        if fnmatch(name, pattern):
            return True
    return False


def file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class PackageManager:
    """Manages package loading, saving, and local storage."""

    def __init__(self, cache_dir: Path | None = None):
        """
        Initialize the package manager.

        Args:
            cache_dir: Directory for cached packages. Defaults to ~/.uvpkg/cache
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".uvpkg" / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.packages_dir = self.cache_dir / "packages"
        self.packages_dir.mkdir(exist_ok=True)

        self.git_cache_dir = self.cache_dir / "git"
        self.git_cache_dir.mkdir(exist_ok=True)

    # --- Loading ---

    def load(self, source: str | Path) -> Package:
        """
        Load a package from various sources.

        Args:
            source: Package name, local path, or git URL

        Returns:
            Loaded Package object
        """
        source_str = str(source)

        # Git URL
        if source_str.startswith(("git@", "https://", "http://", "ssh://")):
            return self._load_from_git(source_str)

        # Local path
        path = Path(source_str).resolve()
        if path.exists():
            return self._load_from_path(path)

        # Try as package name from cache
        cached = self._find_cached(source_str)
        if cached:
            return self._load_from_path(cached)

        raise FileNotFoundError(f"Package not found: {source}")

    def _load_from_path(self, path: Path) -> Package:
        """Load a package from a local directory."""
        manifest_path = self._find_manifest(path)
        if manifest_path is None:
            raise FileNotFoundError(f"No uvpkg.yml found in {path}")

        manifest = self._parse_manifest(manifest_path)

        # Collect all files
        files: list[PackageFile] = []
        for file_path in self._walk_package_files(path):
            rel_path = file_path.relative_to(path)
            try:
                content = file_path.read_text(encoding="utf-8")
                files.append(
                    PackageFile(path=str(rel_path), content=content, encoding="utf-8")
                )
            except UnicodeDecodeError:
                # Skip binary files
                pass

        return Package(manifest=manifest, files=files, source_path=path)

    def _load_from_git(self, url: str, ref: str | None = None, subdir: str | None = None) -> Package:
        """Clone and load a package from a git repository."""
        # Generate cache key from URL
        cache_key = hashlib.sha256(url.encode()).hexdigest()[:16]
        clone_dir = self.git_cache_dir / cache_key

        # Clone or update
        if clone_dir.exists():
            subprocess.run(
                ["git", "fetch", "--all"],
                cwd=clone_dir,
                check=True,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "clone", url, str(clone_dir)],
                check=True,
                capture_output=True,
            )

        # Checkout ref if specified
        if ref:
            subprocess.run(
                ["git", "checkout", ref],
                cwd=clone_dir,
                check=True,
                capture_output=True,
            )

        # Load from subdirectory if specified
        load_path = clone_dir / subdir if subdir else clone_dir
        return self._load_from_path(load_path)

    def _find_cached(self, name: str) -> Path | None:
        """Find a cached package by name."""
        # Check versioned directories
        for version_dir in self.packages_dir.iterdir():
            if not version_dir.is_dir():
                continue
            pkg_dir = version_dir / name
            if pkg_dir.exists() and self._find_manifest(pkg_dir):
                return pkg_dir
        return None

    def _find_manifest(self, directory: Path) -> Path | None:
        """Find the manifest file in a directory."""
        for filename in MANIFEST_FILENAMES:
            manifest_path = directory / filename
            if manifest_path.exists():
                return manifest_path
        return None

    def _parse_manifest(self, path: Path) -> PackageManifest:
        """Parse a manifest file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Normalize dependency formats
        if "packages" in data:
            data["packages"] = self._normalize_dependencies(data["packages"])
        if "dev-packages" in data:
            data["dev-packages"] = self._normalize_dependencies(data["dev-packages"])

        return PackageManifest.model_validate(data)

    def _normalize_dependencies(
        self, deps: dict[str, str | dict]
    ) -> dict[str, PackageDependency | str]:
        """Normalize dependency specifications."""
        result: dict[str, PackageDependency | str] = {}
        for name, spec in deps.items():
            if isinstance(spec, str):
                result[name] = spec
            else:
                result[name] = PackageDependency.model_validate(spec)
        return result

    def _walk_package_files(self, root: Path) -> Iterator[Path]:
        """Walk all non-junk files in a package directory."""
        for path in root.rglob("*"):
            if path.is_file() and not any(is_junk(p) for p in path.parents) and not is_junk(path):
                yield path

    # --- Saving ---

    def save(
        self,
        package: Package,
        version: str | None = None,
    ) -> Path:
        """
        Save a package to the local cache.

        Args:
            package: Package to save
            version: Version to save as (defaults to manifest version)

        Returns:
            Path to saved package
        """
        version = version or package.version
        pkg_dir = self.packages_dir / version / package.name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        manifest_path = pkg_dir / "uvpkg.yml"
        manifest_data = package.manifest.model_dump(by_alias=True, exclude_none=True)
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        # Write files
        for pkg_file in package.files:
            file_path = pkg_dir / pkg_file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(pkg_file.content, encoding=pkg_file.encoding)

        return pkg_dir

    # --- Discovery ---

    def list_cached(self) -> list[PackageStatus]:
        """List all cached packages."""
        packages: list[PackageStatus] = []

        for version_dir in sorted(self.packages_dir.iterdir(), reverse=True):
            if not version_dir.is_dir():
                continue
            version = version_dir.name

            for pkg_dir in version_dir.iterdir():
                if not pkg_dir.is_dir():
                    continue

                manifest_path = self._find_manifest(pkg_dir)
                if manifest_path is None:
                    continue

                try:
                    manifest = self._parse_manifest(manifest_path)
                    packages.append(
                        PackageStatus(
                            name=manifest.name,
                            installed_version=version,
                            source=DependencySource.REGISTRY,
                            source_path=str(pkg_dir),
                        )
                    )
                except Exception:
                    pass

        return packages

    def delete(self, name: str, version: str | None = None) -> bool:
        """
        Delete a package from the cache.

        Args:
            name: Package name
            version: Specific version to delete (all versions if None)

        Returns:
            True if any packages were deleted
        """
        deleted = False

        for version_dir in self.packages_dir.iterdir():
            if not version_dir.is_dir():
                continue
            if version and version_dir.name != version:
                continue

            pkg_dir = version_dir / name
            if pkg_dir.exists():
                shutil.rmtree(pkg_dir)
                deleted = True

                # Clean up empty version directory
                if not any(version_dir.iterdir()):
                    version_dir.rmdir()

        return deleted

    # --- Package Creation ---

    def create(
        self,
        name: str,
        directory: Path | None = None,
        description: str | None = None,
        author: str | None = None,
    ) -> Package:
        """
        Create a new package.

        Args:
            name: Package name
            directory: Directory to create package in (defaults to current dir / name)
            description: Package description
            author: Package author

        Returns:
            Created Package object
        """
        if directory is None:
            directory = Path.cwd() / name

        directory.mkdir(parents=True, exist_ok=True)

        manifest = PackageManifest(
            name=name,
            version="0.1.0",
            description=description,
            author=author,
        )

        # Create manifest file
        manifest_path = directory / "uvpkg.yml"
        manifest_data = manifest.model_dump(by_alias=True, exclude_none=True)
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

        # Create default directories
        (directory / "rules").mkdir(exist_ok=True)
        (directory / "commands").mkdir(exist_ok=True)

        # Create a sample rule file
        sample_rule = directory / "rules" / "example.md"
        sample_rule.write_text(
            f"# {name}\n\nAdd your coding rules here.\n",
            encoding="utf-8",
        )

        return self.load(directory)

    # --- Workspace Manifest ---

    def load_workspace_manifest(self, workspace: Path) -> PackageManifest | None:
        """Load the workspace manifest (uvpkg.yml in workspace root)."""
        manifest_path = self._find_manifest(workspace)
        if manifest_path is None:
            return None
        return self._parse_manifest(manifest_path)

    def save_workspace_manifest(self, workspace: Path, manifest: PackageManifest) -> Path:
        """Save the workspace manifest."""
        manifest_path = workspace / "uvpkg.yml"
        manifest_data = manifest.model_dump(by_alias=True, exclude_none=True)
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
        return manifest_path

    def init_workspace(self, workspace: Path, name: str | None = None) -> PackageManifest:
        """Initialize a workspace with a uvpkg.yml manifest."""
        if name is None:
            name = workspace.name

        manifest = PackageManifest(
            name=name,
            version="0.1.0",
            partial=True,  # workspace manifests are partial by default
        )

        self.save_workspace_manifest(workspace, manifest)
        return manifest
