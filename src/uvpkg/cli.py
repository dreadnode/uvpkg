"""
Command-line interface for uvpkg.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from uvpkg.installer import Installer
from uvpkg.manager import PackageManager
from uvpkg.models import ConflictStrategy, InstallOptions, PackageDependency
from uvpkg.platforms import detect_platforms, get_platform, list_platforms

console = Console()


@click.group()
@click.option("--cwd", "-C", type=click.Path(exists=True, path_type=Path), help="Working directory")
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, cwd: Path | None) -> None:
    """uvpkg - Universal AI coding package manager."""
    ctx.ensure_object(dict)
    ctx.obj["cwd"] = cwd or Path.cwd()
    ctx.obj["manager"] = PackageManager()


# --- Package Commands ---


@cli.command()
@click.argument("name")
@click.option("--path", "-p", type=click.Path(path_type=Path), help="Directory to create package in")
@click.option("--description", "-d", help="Package description")
@click.option("--author", "-a", help="Package author")
@click.pass_context
def new(
    ctx: click.Context,
    name: str,
    path: Path | None,
    description: str | None,
    author: str | None,
) -> None:
    """Create a new package."""
    manager: PackageManager = ctx.obj["manager"]
    cwd: Path = ctx.obj["cwd"]

    if path is None:
        path = cwd / name

    try:
        package = manager.create(name, path, description, author)
        console.print(f"[green]Created package:[/green] {package.name}")
        console.print(f"  Location: {path}")
        console.print("\nNext steps:")
        console.print(f"  cd {path}")
        console.print("  # Add your rules, commands, and config files")
        console.print(f"  uvpkg install {path}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@cli.command()
@click.argument("source", required=False)
@click.option("--force", "-f", is_flag=True, help="Force overwrite existing files")
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be installed")
@click.option("--platform", "-p", multiple=True, help="Install to specific platform(s)")
@click.option("--dev", is_flag=True, help="Install as dev dependency")
@click.option("--git", "-g", help="Git repository URL")
@click.option("--ref", help="Git ref (branch, tag, commit)")
@click.option("--path", type=click.Path(exists=True, path_type=Path), help="Local path")
@click.pass_context
def install(
    ctx: click.Context,
    source: str | None,
    force: bool,
    dry_run: bool,
    platform: tuple[str, ...],
    dev: bool,
    git: str | None,
    ref: str | None,
    path: Path | None,
) -> None:
    """Install a package to the workspace.

    SOURCE can be a package name, local path, or git URL.
    If no source is provided, installs all packages from uvpkg.yml.
    """
    cwd: Path = ctx.obj["cwd"]
    manager: PackageManager = ctx.obj["manager"]
    installer = Installer(cwd, manager)

    options = InstallOptions(
        dry_run=dry_run,
        force=force,
        dev=dev,
        platforms=list(platform) if platform else None,
        conflict=ConflictStrategy.OVERWRITE if force else ConflictStrategy.PROMPT,
    )

    # Determine source
    if git:
        dep = PackageDependency(git=git, ref=ref)
        results = [installer.install(dep, options)]
    elif path:
        results = [installer.install(path, options)]
    elif source:
        results = [installer.install(source, options)]
    else:
        # Install all from manifest
        results = installer.sync(options)

    # Report results
    success_count = 0
    for result in results:
        if result.success:
            success_count += 1
            if dry_run:
                console.print(f"[blue]Would install:[/blue] {result.package_name}")
            else:
                console.print(f"[green]Installed:[/green] {result.package_name}")

            if result.files_written:
                for f in result.files_written[:5]:
                    console.print(f"  + {f}")
                if len(result.files_written) > 5:
                    console.print(f"  ... and {len(result.files_written) - 5} more")
        else:
            console.print(f"[red]Failed:[/red] {result.package_name}")
            for error in result.errors:
                console.print(f"  {error}")

    if not results:
        console.print("[yellow]No packages to install[/yellow]")
    elif success_count == len(results):
        action = "would be installed" if dry_run else "installed"
        console.print(f"\n[green]{success_count} package(s) {action}[/green]")
    else:
        console.print(f"\n[yellow]{success_count}/{len(results)} packages installed[/yellow]")


@cli.command()
@click.argument("package_name")
@click.pass_context
def uninstall(ctx: click.Context, package_name: str) -> None:
    """Uninstall a package from the workspace."""
    cwd: Path = ctx.obj["cwd"]
    manager: PackageManager = ctx.obj["manager"]
    installer = Installer(cwd, manager)

    result = installer.uninstall(package_name)

    if result.success:
        console.print(f"[green]Uninstalled:[/green] {result.package_name}")
        if result.files_removed:
            for f in result.files_removed[:5]:
                console.print(f"  - {f}")
            if len(result.files_removed) > 5:
                console.print(f"  ... and {len(result.files_removed) - 5} more")
    else:
        console.print(f"[red]Failed:[/red] {result.package_name}")
        for error in result.errors:
            console.print(f"  {error}")


@cli.command()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Sync all packages from uvpkg.yml to workspace."""
    ctx.invoke(install)


# --- List/Status Commands ---


@cli.command("list")
@click.option("--cached", "-c", is_flag=True, help="List cached packages instead of installed")
@click.pass_context
def list_packages(ctx: click.Context, cached: bool) -> None:
    """List installed or cached packages."""
    cwd: Path = ctx.obj["cwd"]
    manager: PackageManager = ctx.obj["manager"]

    if cached:
        packages = manager.list_cached()
        title = "Cached Packages"
    else:
        installer = Installer(cwd, manager)
        packages = installer.status()
        title = "Installed Packages"

    if not packages:
        console.print(f"[yellow]No {title.lower()}[/yellow]")
        return

    table = Table(title=title)
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Source")
    table.add_column("Files", justify="right")

    for pkg in packages:
        source_str = pkg.source.value
        if pkg.source_path:
            source_str = f"{pkg.source.value}: {pkg.source_path}"

        table.add_row(
            pkg.name,
            pkg.installed_version or "-",
            source_str,
            str(len(pkg.files)) if pkg.files else "-",
        )

    console.print(table)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show status of installed packages."""
    ctx.invoke(list_packages, cached=False)


# --- Platform Commands ---


@cli.command()
@click.pass_context
def platforms(ctx: click.Context) -> None:
    """List all supported platforms."""
    cwd: Path = ctx.obj["cwd"]

    detected = detect_platforms(cwd)
    detected_names = {p.name for p in detected}

    table = Table(title="Supported Platforms")
    table.add_column("Name", style="cyan")
    table.add_column("Directory")
    table.add_column("Detected", justify="center")
    table.add_column("Aliases")

    for platform in list_platforms():
        is_detected = "✓" if platform.name in detected_names else ""
        table.add_row(
            platform.name,
            platform.root_dir,
            f"[green]{is_detected}[/green]" if is_detected else "",
            ", ".join(platform.aliases),
        )

    console.print(table)


# --- Workspace Commands ---


@cli.command()
@click.option("--name", "-n", help="Workspace name (defaults to directory name)")
@click.pass_context
def init(ctx: click.Context, name: str | None) -> None:
    """Initialize a workspace with uvpkg.yml."""
    cwd: Path = ctx.obj["cwd"]
    manager: PackageManager = ctx.obj["manager"]

    manifest_path = cwd / "uvpkg.yml"
    if manifest_path.exists():
        console.print("[yellow]uvpkg.yml already exists[/yellow]")
        return

    manifest = manager.init_workspace(cwd, name)
    console.print(f"[green]Initialized workspace:[/green] {manifest.name}")
    console.print(f"  Created: {manifest_path}")


@cli.command()
@click.argument("package_name")
@click.pass_context
def show(ctx: click.Context, package_name: str) -> None:
    """Show details of a package."""
    manager: PackageManager = ctx.obj["manager"]

    try:
        package = manager.load(package_name)

        console.print(f"[cyan]{package.name}[/cyan] v{package.version}")
        if package.manifest.description:
            console.print(f"  {package.manifest.description}")
        if package.manifest.author:
            console.print(f"  Author: {package.manifest.author}")
        if package.manifest.homepage:
            console.print(f"  Homepage: {package.manifest.homepage}")

        console.print(f"\n  Files: {len(package.files)}")
        for f in package.files[:10]:
            console.print(f"    {f.path}")
        if len(package.files) > 10:
            console.print(f"    ... and {len(package.files) - 10} more")

        if package.manifest.packages:
            console.print(f"\n  Dependencies: {len(package.manifest.packages)}")
            for name in package.manifest.packages:
                console.print(f"    {name}")

    except FileNotFoundError:
        console.print(f"[red]Package not found:[/red] {package_name}")
        raise SystemExit(1)


@cli.command()
@click.argument("package_name")
@click.option("--version", "-v", help="Version to delete (all if not specified)")
@click.option("--force", "-f", is_flag=True, help="Don't ask for confirmation")
@click.pass_context
def delete(ctx: click.Context, package_name: str, version: str | None, force: bool) -> None:
    """Delete a package from the cache."""
    manager: PackageManager = ctx.obj["manager"]

    if not force:
        version_str = f" v{version}" if version else ""
        if not click.confirm(f"Delete {package_name}{version_str} from cache?"):
            return

    if manager.delete(package_name, version):
        console.print(f"[green]Deleted:[/green] {package_name}")
    else:
        console.print(f"[yellow]Package not found in cache:[/yellow] {package_name}")


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
