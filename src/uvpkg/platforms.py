"""
Platform definitions for AI coding assistants.

Defines file mappings and transformations for each supported platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileMapping:
    """Mapping from package file pattern to platform-specific location."""

    package_pattern: str  # glob pattern in package (e.g., "rules/*.md")
    platform_path: str  # target path in platform dir (e.g., "rules/{name}.md")
    merge_strategy: str = "replace"  # replace, deep, shallow, composite


@dataclass
class Platform:
    """Definition of an AI coding platform."""

    name: str
    root_dir: str  # e.g., ".claude", ".cursor"
    root_file: str | None = None  # detection file (e.g., "CLAUDE.md")
    aliases: list[str] = field(default_factory=list)

    # File mappings: package -> platform
    export_mappings: list[FileMapping] = field(default_factory=list)

    # File mappings: platform -> package (for save)
    import_mappings: list[FileMapping] = field(default_factory=list)

    # MCP config format
    mcp_format: str = "json"  # json or toml
    mcp_path: str | None = None  # path to MCP config file

    def detect(self, workspace: Path) -> bool:
        """Check if this platform is configured in a workspace."""
        platform_dir = workspace / self.root_dir
        if not platform_dir.exists():
            return False
        if self.root_file:
            return (platform_dir / self.root_file).exists() or (
                workspace / self.root_file
            ).exists()
        return True

    def get_config_dir(self, workspace: Path) -> Path:
        """Get the platform configuration directory."""
        return workspace / self.root_dir

    def ensure_config_dir(self, workspace: Path) -> Path:
        """Ensure the platform configuration directory exists."""
        config_dir = self.get_config_dir(workspace)
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir


# Platform Definitions

CLAUDE_CODE = Platform(
    name="Claude Code",
    root_dir=".claude",
    root_file="CLAUDE.md",
    aliases=["claude", "claude-code", "anthropic"],
    mcp_format="json",
    mcp_path=".claude/mcp.json",
    export_mappings=[
        FileMapping("rules/**/*.md", "rules/{path}", "composite"),
        FileMapping("commands/**/*.md", "commands/{path}", "replace"),
        FileMapping("agents/**/*.md", "agents/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
        FileMapping("settings.json", "settings.json", "deep"),
        FileMapping("CLAUDE.md", "../CLAUDE.md", "composite"),
        FileMapping("AGENTS.md", "../AGENTS.md", "composite"),
    ],
    import_mappings=[
        FileMapping(".claude/rules/**/*.md", "rules/{path}", "replace"),
        FileMapping(".claude/commands/**/*.md", "commands/{path}", "replace"),
        FileMapping("CLAUDE.md", "CLAUDE.md", "replace"),
        FileMapping("AGENTS.md", "AGENTS.md", "replace"),
    ],
)

CURSOR = Platform(
    name="Cursor",
    root_dir=".cursor",
    root_file="rules",
    aliases=["cursor"],
    mcp_format="json",
    mcp_path=".cursor/mcp.json",
    export_mappings=[
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("rules/**/*.mdc", "rules/{path}", "replace"),
        FileMapping("commands/**/*.json", "commands/{path}", "replace"),
        FileMapping("agents/**/*.json", "agents/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".cursor/rules/**/*", "rules/{path}", "replace"),
        FileMapping(".cursor/commands/**/*", "commands/{path}", "replace"),
        FileMapping(".cursorrules", "rules/cursorrules.md", "replace"),
    ],
)

WINDSURF = Platform(
    name="Windsurf",
    root_dir=".windsurf",
    root_file="rules",
    aliases=["windsurf", "codeium"],
    mcp_format="json",
    mcp_path=".windsurf/mcp.json",
    export_mappings=[
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".windsurf/rules/**/*", "rules/{path}", "replace"),
        FileMapping(".windsurfrules", "rules/windsurfrules.md", "replace"),
    ],
)

CODEX = Platform(
    name="Codex CLI",
    root_dir=".codex",
    root_file="config.yaml",
    aliases=["codex", "codex-cli", "openai-codex"],
    mcp_format="toml",
    mcp_path=".codex/mcp.toml",
    export_mappings=[
        FileMapping("prompts/**/*.md", "prompts/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("config.yaml", "config.yaml", "deep"),
        FileMapping("mcp.toml", "mcp.toml", "deep"),
    ],
    import_mappings=[
        FileMapping(".codex/prompts/**/*", "prompts/{path}", "replace"),
        FileMapping(".codex/skills/**/*", "skills/{path}", "replace"),
    ],
)

OPENCODE = Platform(
    name="OpenCode",
    root_dir=".opencode",
    root_file="config.json",
    aliases=["opencode"],
    mcp_format="json",
    mcp_path=".opencode/mcp.json",
    export_mappings=[
        FileMapping("commands/**/*.md", "commands/{path}", "replace"),
        FileMapping("agents/**/*.md", "agents/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("config.json", "config.json", "deep"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".opencode/commands/**/*", "commands/{path}", "replace"),
        FileMapping(".opencode/agents/**/*", "agents/{path}", "replace"),
    ],
)

KILO_CODE = Platform(
    name="Kilo Code",
    root_dir=".kilocode",
    root_file="rules",
    aliases=["kilocode", "kilo"],
    mcp_format="json",
    mcp_path=".kilocode/mcp.json",
    export_mappings=[
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("workflows/**/*.md", "workflows/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".kilocode/rules/**/*", "rules/{path}", "replace"),
    ],
)

ROO_CODE = Platform(
    name="Roo Code",
    root_dir=".roo",
    root_file="rules",
    aliases=["roo", "roocode"],
    mcp_format="json",
    mcp_path=".roo/mcp.json",
    export_mappings=[
        FileMapping("commands/**/*.md", "commands/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".roo/rules/**/*", "rules/{path}", "replace"),
    ],
)

AUGMENT = Platform(
    name="Augment Code",
    root_dir=".augment",
    root_file="rules",
    aliases=["augment", "augment-code"],
    mcp_format="json",
    mcp_path=".augment/mcp.json",
    export_mappings=[
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("commands/**/*.md", "commands/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".augment/rules/**/*", "rules/{path}", "replace"),
    ],
)

WARP = Platform(
    name="Warp",
    root_dir=".warp",
    root_file="WARP.md",
    aliases=["warp"],
    mcp_format="json",
    mcp_path=".warp/mcp.json",
    export_mappings=[
        FileMapping("WARP.md", "../WARP.md", "composite"),
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping("WARP.md", "WARP.md", "replace"),
        FileMapping(".warp/rules/**/*", "rules/{path}", "replace"),
    ],
)

FACTORY = Platform(
    name="Factory AI",
    root_dir=".factory",
    root_file="config.json",
    aliases=["factory", "factory-ai"],
    mcp_format="json",
    mcp_path=".factory/mcp.json",
    export_mappings=[
        FileMapping("commands/**/*.md", "commands/{path}", "replace"),
        FileMapping("droids/**/*.json", "droids/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".factory/commands/**/*", "commands/{path}", "replace"),
        FileMapping(".factory/droids/**/*", "droids/{path}", "replace"),
    ],
)

QWEN = Platform(
    name="Qwen Code",
    root_dir=".qwen",
    root_file="settings.json",
    aliases=["qwen", "qwen-code"],
    mcp_format="json",
    mcp_path=".qwen/mcp.json",
    export_mappings=[
        FileMapping("agents/**/*.json", "agents/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("settings.json", "settings.json", "deep"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".qwen/agents/**/*", "agents/{path}", "replace"),
    ],
)

KIRO = Platform(
    name="Kiro",
    root_dir=".kiro",
    root_file="settings.json",
    aliases=["kiro"],
    mcp_format="json",
    mcp_path=".kiro/mcp.json",
    export_mappings=[
        FileMapping("steering/**/*.md", "steering/{path}", "replace"),
        FileMapping("settings.json", "settings.json", "deep"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".kiro/steering/**/*", "steering/{path}", "replace"),
    ],
)

ANTIGRAVITY = Platform(
    name="Google Antigravity",
    root_dir=".agent",
    root_file="rules",
    aliases=["antigravity", "google-agent", "agent"],
    mcp_format="json",
    mcp_path=".agent/mcp.json",
    export_mappings=[
        FileMapping("rules/**/*.md", "rules/{path}", "replace"),
        FileMapping("workflows/**/*.md", "workflows/{path}", "replace"),
        FileMapping("skills/**/*.md", "skills/{path}", "replace"),
        FileMapping("mcp.json", "mcp.json", "deep"),
    ],
    import_mappings=[
        FileMapping(".agent/rules/**/*", "rules/{path}", "replace"),
    ],
)

# Registry of all platforms
PLATFORMS: dict[str, Platform] = {
    "claude": CLAUDE_CODE,
    "cursor": CURSOR,
    "windsurf": WINDSURF,
    "codex": CODEX,
    "opencode": OPENCODE,
    "kilocode": KILO_CODE,
    "roo": ROO_CODE,
    "augment": AUGMENT,
    "warp": WARP,
    "factory": FACTORY,
    "qwen": QWEN,
    "kiro": KIRO,
    "antigravity": ANTIGRAVITY,
}


def get_platform(name: str) -> Platform | None:
    """Get a platform by name or alias."""
    name_lower = name.lower()

    # Direct lookup
    if name_lower in PLATFORMS:
        return PLATFORMS[name_lower]

    # Check aliases
    for platform in PLATFORMS.values():
        if name_lower in [a.lower() for a in platform.aliases]:
            return platform

    return None


def list_platforms() -> list[Platform]:
    """List all available platforms."""
    return list(PLATFORMS.values())


def detect_platforms(workspace: Path) -> list[Platform]:
    """Detect which platforms are configured in a workspace."""
    return [p for p in PLATFORMS.values() if p.detect(workspace)]


def get_platform_by_dir(root_dir: str) -> Platform | None:
    """Get a platform by its root directory name."""
    for platform in PLATFORMS.values():
        if platform.root_dir == root_dir:
            return platform
    return None
