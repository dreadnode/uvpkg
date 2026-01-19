# uvpkg

Universal AI coding package manager - a Python/UV reimplementation of [openpackage](https://github.com/enulus/openpackage).

Turn your AI coding setups into reusable packages that work across multiple platforms.

## Features

- **Multi-platform support**: Claude Code, Cursor, Windsurf, Codex, OpenCode, and more
- **Multiple sources**: Install from local paths, Git repositories, or registries
- **File transformations**: Deep merge, composite merge, variable substitution
- **Workspace tracking**: Lock file tracks installed files for clean uninstalls
- **Pure Python/UV**: No Node.js required

## Installation

```bash
# With uv (recommended)
uv tool install uvpkg

# With pip
pip install uvpkg

# From source
git clone https://github.com/dreadnode/uvpkg
cd uvpkg
uv sync
uv run uvpkg --help
```

## Quick Start

```bash
# Initialize a workspace
uvpkg init

# Create a new package
uvpkg new my-rules

# Install a package from local path
uvpkg install ./my-rules

# Install from git
uvpkg install --git https://github.com/user/ai-rules

# List installed packages
uvpkg list

# Uninstall a package
uvpkg uninstall my-rules

# Sync all packages from openpackage.yml
uvpkg sync
```

## Package Structure

A uvpkg package is a directory with an `openpackage.yml` manifest:

```
my-package/
├── openpackage.yml           # Package manifest
├── rules/              # Coding rules (markdown)
│   └── style.md
├── commands/           # Custom commands
│   └── test.md
├── mcp.json            # MCP server configuration
└── CLAUDE.md           # Claude-specific instructions
```

### Manifest (openpackage.yml)

```yaml
name: my-package
version: 0.1.0
description: My AI coding rules
author: Your Name

packages:
  base-rules:
    path: ../base-rules
  community-rules:
    git: https://github.com/user/rules
    ref: main
```

## Supported Platforms

| Platform | Directory | Detection |
|----------|-----------|-----------|
| Claude Code | `.claude` | `CLAUDE.md` |
| Cursor | `.cursor` | `rules/` |
| Windsurf | `.windsurf` | `rules/` |
| Codex CLI | `.codex` | `config.yaml` |
| OpenCode | `.opencode` | `config.json` |
| Kilo Code | `.kilocode` | `rules/` |
| Roo Code | `.roo` | `rules/` |
| Augment | `.augment` | `rules/` |
| Warp | `.warp` | `WARP.md` |
| Factory AI | `.factory` | `config.json` |
| Qwen Code | `.qwen` | `settings.json` |
| Kiro | `.kiro` | `settings.json` |
| Google Antigravity | `.agent` | `rules/` |

## CLI Commands

```
uvpkg new <name>           Create a new package
uvpkg install [source]     Install a package (or all from manifest)
uvpkg uninstall <name>     Uninstall a package
uvpkg sync                 Sync all packages from openpackage.yml
uvpkg list                 List installed packages
uvpkg list --cached        List cached packages
uvpkg status               Show installation status
uvpkg platforms            List supported platforms
uvpkg init                 Initialize workspace with openpackage.yml
uvpkg show <name>          Show package details
uvpkg delete <name>        Delete from cache
```

## File Mappings

uvpkg maps package files to platform-specific locations:

| Package Path | Claude Code | Cursor | Windsurf |
|--------------|-------------|--------|----------|
| `rules/*.md` | `.claude/rules/` | `.cursor/rules/` | `.windsurf/rules/` |
| `commands/*.md` | `.claude/commands/` | `.cursor/commands/` | - |
| `mcp.json` | `.claude/mcp.json` | `.cursor/mcp.json` | `.windsurf/mcp.json` |
| `CLAUDE.md` | `CLAUDE.md` | - | - |

## Merge Strategies

- **replace**: Overwrite target file completely
- **deep**: Deep merge JSON/YAML preserving nested structures
- **shallow**: Shallow merge (top-level keys only)
- **composite**: Append with delimiter (for markdown files)

## Development

```bash
# Clone and setup
git clone https://github.com/dreadnode/uvpkg
cd uvpkg
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check src/

# Build
uv build
```

## License

Apache-2.0
