"""
Installer for syncing packages to workspaces across platforms.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from uvpkg.manager import PackageManager
from uvpkg.models import (
    ConflictStrategy,
    DependencySource,
    InstallOptions,
    MergeStrategy,
    Package,
    PackageDependency,
    PackageManifest,
    PackageStatus,
)
from uvpkg.platforms import (
    FileMapping,
    Platform,
    detect_platforms,
    get_platform,
    list_platforms,
)


@dataclass
class InstallResult:
    """Result of an install operation."""

    success: bool
    package_name: str
    files_written: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class UninstallResult:
    """Result of an uninstall operation."""

    success: bool
    package_name: str
    files_removed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Installer:
    """Installs and uninstalls packages to/from workspaces."""

    def __init__(self, workspace: Path, manager: PackageManager | None = None):
        """
        Initialize the installer.

        Args:
            workspace: Workspace directory
            manager: PackageManager instance (created if not provided)
        """
        self.workspace = workspace.resolve()
        self.manager = manager or PackageManager()

        # Lock file tracks installed packages and files
        self.lock_file = self.workspace / "uvpkg.lock"

        # Load or create workspace manifest
        self.manifest = self.manager.load_workspace_manifest(self.workspace)

    def install(
        self,
        source: str | Path | PackageDependency,
        options: InstallOptions | None = None,
    ) -> InstallResult:
        """
        Install a package to the workspace.

        Args:
            source: Package source (path, git URL, or dependency spec)
            options: Installation options

        Returns:
            InstallResult with details
        """
        options = options or InstallOptions()
        result = InstallResult(success=False, package_name="")

        try:
            # Load the package
            if isinstance(source, PackageDependency):
                package = self._load_from_dependency(source)
            else:
                package = self.manager.load(source)

            result.package_name = package.name

            # Determine target platforms
            if options.platforms:
                platforms = [get_platform(p) for p in options.platforms if get_platform(p)]
            else:
                # Auto-detect or use all
                platforms = detect_platforms(self.workspace) or list_platforms()

            if not platforms:
                result.errors.append("No platforms detected or specified")
                return result

            # Install to each platform
            for platform in platforms:
                self._install_to_platform(package, platform, options, result)

            # Update workspace manifest
            self._update_manifest(package, source)

            # Update lock file
            self._update_lock(package, result.files_written)

            result.success = len(result.errors) == 0

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _load_from_dependency(self, dep: PackageDependency) -> Package:
        """Load a package from a dependency specification."""
        if dep.source == DependencySource.PATH:
            path = dep.resolve_path(self.workspace)
            if path is None:
                raise ValueError("Invalid path dependency")
            return self.manager.load(path)
        elif dep.source == DependencySource.GIT:
            if dep.git is None:
                raise ValueError("Invalid git dependency")
            return self.manager._load_from_git(dep.git, dep.ref, dep.subdir)
        else:
            raise ValueError(f"Registry dependencies not yet supported: {dep}")

    def _install_to_platform(
        self,
        package: Package,
        platform: Platform,
        options: InstallOptions,
        result: InstallResult,
    ) -> None:
        """Install package files to a specific platform."""
        platform_dir = platform.ensure_config_dir(self.workspace)

        for mapping in platform.export_mappings:
            matched_files = self._match_files(package, mapping.package_pattern)

            for pkg_file in matched_files:
                target_path = self._resolve_target_path(
                    pkg_file.path,
                    mapping,
                    platform_dir,
                )

                # Handle dry run
                if options.dry_run:
                    result.files_written.append(str(target_path))
                    continue

                # Check for conflicts
                if target_path.exists() and not options.force:
                    if options.conflict == ConflictStrategy.SKIP:
                        result.files_skipped.append(str(target_path))
                        continue
                    elif options.conflict == ConflictStrategy.BACKUP:
                        backup_path = target_path.with_suffix(target_path.suffix + ".bak")
                        shutil.copy2(target_path, backup_path)

                # Write the file
                try:
                    self._write_file(
                        target_path,
                        pkg_file.content,
                        MergeStrategy(mapping.merge_strategy),
                        options.variables,
                    )
                    result.files_written.append(str(target_path))
                except Exception as e:
                    result.errors.append(f"Failed to write {target_path}: {e}")

    def _match_files(self, package: Package, pattern: str) -> list:
        """Match package files against a glob pattern."""
        from fnmatch import fnmatch

        from uvpkg.models import PackageFile

        matched: list[PackageFile] = []

        # Handle ** glob patterns by converting to fnmatch-compatible patterns
        # rules/**/*.md should match rules/foo.md and rules/sub/foo.md
        if "**" in pattern:
            # Split on ** and create multiple patterns
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix = parts[0].rstrip("/")
                suffix = parts[1].lstrip("/")

                for pkg_file in package.files:
                    path = pkg_file.path
                    # Check if path starts with prefix
                    if prefix and not path.startswith(prefix):
                        continue
                    # Get the remaining path after prefix
                    remaining = path[len(prefix):].lstrip("/") if prefix else path
                    # Check if it matches the suffix pattern
                    if fnmatch(remaining, suffix) or fnmatch(path, pattern.replace("**", "*")):
                        matched.append(pkg_file)
            else:
                # Complex pattern, fall back to simple matching
                for pkg_file in package.files:
                    if fnmatch(pkg_file.path, pattern.replace("**", "*")):
                        matched.append(pkg_file)
        else:
            # Simple pattern without **
            for pkg_file in package.files:
                if fnmatch(pkg_file.path, pattern):
                    matched.append(pkg_file)

        return matched

    def _resolve_target_path(
        self,
        source_path: str,
        mapping: FileMapping,
        platform_dir: Path,
    ) -> Path:
        """Resolve the target path for a file."""
        target_pattern = mapping.platform_path

        # Extract path components
        source = Path(source_path)
        name = source.stem
        ext = source.suffix
        parent = str(source.parent)

        # For {path} placeholder, we need to handle the mapping prefix
        # e.g., if pattern is "rules/**/*.md" and source is "rules/example.md"
        # then {path} should be "example.md" not "rules/example.md"
        pkg_pattern = mapping.package_pattern
        relative_path = source_path

        # Strip the directory prefix from the pattern
        if "**" in pkg_pattern:
            prefix = pkg_pattern.split("**")[0].rstrip("/")
            if prefix and source_path.startswith(prefix + "/"):
                relative_path = source_path[len(prefix) + 1:]
        elif "/" in pkg_pattern:
            # For patterns like "rules/*.md", strip "rules/"
            prefix = pkg_pattern.rsplit("/", 1)[0]
            if prefix and source_path.startswith(prefix + "/"):
                relative_path = source_path[len(prefix) + 1:]

        # Substitute placeholders
        target = target_pattern.format(
            path=relative_path,
            name=name,
            ext=ext,
            parent=parent,
        )

        # Handle parent directory references
        if target.startswith("../"):
            return (platform_dir.parent / target[3:]).resolve()

        return (platform_dir / target).resolve()

    def _write_file(
        self,
        path: Path,
        content: str,
        merge: MergeStrategy,
        variables: dict[str, str],
    ) -> None:
        """Write content to a file with merge strategy."""
        # Substitute variables
        for key, value in variables.items():
            content = content.replace(f"${{{key}}}", value)
            content = content.replace(f"${key}", value)

        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists() or merge == MergeStrategy.REPLACE:
            path.write_text(content, encoding="utf-8")
            return

        existing = path.read_text(encoding="utf-8")

        if merge == MergeStrategy.COMPOSITE:
            # Append with delimiter for markdown files
            delimiter = "\n\n---\n\n"
            if content not in existing:
                path.write_text(existing + delimiter + content, encoding="utf-8")

        elif merge == MergeStrategy.DEEP:
            # Deep merge for JSON/YAML
            merged = self._deep_merge(existing, content, path.suffix)
            path.write_text(merged, encoding="utf-8")

        elif merge == MergeStrategy.SHALLOW:
            # Shallow merge for JSON/YAML
            merged = self._shallow_merge(existing, content, path.suffix)
            path.write_text(merged, encoding="utf-8")

    def _deep_merge(self, existing: str, new: str, suffix: str) -> str:
        """Deep merge two files."""
        if suffix == ".json":
            existing_data = json.loads(existing)
            new_data = json.loads(new)
            merged = self._merge_dicts(existing_data, new_data, deep=True)
            return json.dumps(merged, indent=2)
        elif suffix in (".yml", ".yaml"):
            existing_data = yaml.safe_load(existing) or {}
            new_data = yaml.safe_load(new) or {}
            merged = self._merge_dicts(existing_data, new_data, deep=True)
            return yaml.dump(merged, default_flow_style=False)
        return new

    def _shallow_merge(self, existing: str, new: str, suffix: str) -> str:
        """Shallow merge two files."""
        if suffix == ".json":
            existing_data = json.loads(existing)
            new_data = json.loads(new)
            merged = {**existing_data, **new_data}
            return json.dumps(merged, indent=2)
        elif suffix in (".yml", ".yaml"):
            existing_data = yaml.safe_load(existing) or {}
            new_data = yaml.safe_load(new) or {}
            merged = {**existing_data, **new_data}
            return yaml.dump(merged, default_flow_style=False)
        return new

    def _merge_dicts(self, base: dict, override: dict, deep: bool = True) -> dict:
        """Merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value
        return result

    def _update_manifest(
        self,
        package: Package,
        source: str | Path | PackageDependency,
    ) -> None:
        """Update workspace manifest with installed package."""
        if self.manifest is None:
            self.manifest = self.manager.init_workspace(self.workspace)

        # Create dependency entry
        if isinstance(source, PackageDependency):
            dep = source
        elif isinstance(source, Path) or Path(str(source)).exists():
            dep = PackageDependency(path=str(source))
        elif str(source).startswith(("git@", "https://", "http://")):
            dep = PackageDependency(git=str(source))
        else:
            dep = PackageDependency(version=package.version)

        self.manifest.packages[package.name] = dep
        self.manager.save_workspace_manifest(self.workspace, self.manifest)

    def _update_lock(self, package: Package, files: list[str]) -> None:
        """Update the lock file with installed package."""
        lock_data = self._load_lock()

        lock_data["packages"] = lock_data.get("packages", {})
        lock_data["packages"][package.name] = {
            "version": package.version,
            "files": files,
        }

        self._save_lock(lock_data)

    def _load_lock(self) -> dict[str, Any]:
        """Load the lock file."""
        if self.lock_file.exists():
            with open(self.lock_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_lock(self, data: dict[str, Any]) -> None:
        """Save the lock file."""
        with open(self.lock_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def uninstall(self, package_name: str) -> UninstallResult:
        """
        Uninstall a package from the workspace.

        Args:
            package_name: Name of package to uninstall

        Returns:
            UninstallResult with details
        """
        result = UninstallResult(success=False, package_name=package_name)

        lock_data = self._load_lock()
        packages = lock_data.get("packages", {})

        if package_name not in packages:
            result.errors.append(f"Package not installed: {package_name}")
            return result

        # Remove files
        pkg_info = packages[package_name]
        for file_path in pkg_info.get("files", []):
            path = Path(file_path)
            if path.exists():
                try:
                    path.unlink()
                    result.files_removed.append(file_path)

                    # Clean up empty parent directories
                    parent = path.parent
                    while parent != self.workspace and not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                except Exception as e:
                    result.errors.append(f"Failed to remove {file_path}: {e}")

        # Update lock file
        del packages[package_name]
        lock_data["packages"] = packages
        self._save_lock(lock_data)

        # Update manifest
        if self.manifest and package_name in self.manifest.packages:
            del self.manifest.packages[package_name]
            self.manager.save_workspace_manifest(self.workspace, self.manifest)

        result.success = len(result.errors) == 0
        return result

    def sync(self, options: InstallOptions | None = None) -> list[InstallResult]:
        """
        Sync all packages from manifest to workspace.

        Args:
            options: Installation options

        Returns:
            List of InstallResult for each package
        """
        if self.manifest is None:
            return []

        results: list[InstallResult] = []

        for name, dep in self.manifest.all_dependencies(include_dev=True).items():
            result = self.install(dep, options)
            results.append(result)

        return results

    def status(self) -> list[PackageStatus]:
        """
        Get status of all installed packages.

        Returns:
            List of PackageStatus for each installed package
        """
        lock_data = self._load_lock()
        packages = lock_data.get("packages", {})

        statuses: list[PackageStatus] = []
        for name, info in packages.items():
            # Get source from manifest
            dep = self.manifest.get_dependency(name) if self.manifest else None
            source = dep.source if dep else DependencySource.REGISTRY
            source_path = dep.path or dep.git if dep else None

            statuses.append(
                PackageStatus(
                    name=name,
                    installed_version=info.get("version"),
                    source=source,
                    source_path=source_path,
                    files=info.get("files", []),
                )
            )

        return statuses
