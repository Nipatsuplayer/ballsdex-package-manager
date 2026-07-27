# BallsDex Package Manager

A 3rd party package for [BallsDex](https://github.com/Ballsdex-Team/BallsDex-DiscordBot) that provides a web-based admin panel interface for installing, managing, and removing 3rd party packages. No more editing `config/extra.toml` manually!

## Features

- **Install packages** from git repositories via the admin panel
- **Enable/disable** packages without uninstalling
- **Update packages** with git pull + reinstall
- **Uninstall packages** cleanly (pip + files)
- **Zero core file modifications** - uses the existing `extra.toml` mechanism

## How It Works

This package manager integrates with the existing Ballsdex package system:

1. When you install a package via the admin panel, it:
   - Clones the git repository to the `extra/` directory
   - Runs `pip install` (via `uv pip` when available)
   - **Writes the package entry to `config/extra.toml`**
   - Saves metadata to the database (for tracking)

2. On restart, the existing `discover_extra_packages()` reads `extra.toml` and loads all packages

3. The database tracks metadata (install date, logs, version) but `extra.toml` remains the source of truth for package discovery

## Requirements

- Python 3.11+
- BallsDex 3.0.0+
- `git` installed and available in PATH

## Installation

### Bootstrap (First-time Setup)

The package manager itself must be installed via the standard Ballsdex package mechanism. After that, all future packages can be installed through the admin panel.

#### Docker Installation

1. Edit `config/extra.toml` and add:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/Nipatsuplayer/ballsdex-package-manager.git"
path = "packagemanager"
enabled = true
```

2. Rebuild and restart your Docker containers:

```bash
docker compose build
docker compose up -d
```

#### Dockerless Installation

1. Install the package:

```bash
# Make sure your venv is activated
uv pip install git+https://github.com/Nipatsuplayer/ballsdex-package-manager.git
```

2. Edit `config/extra.toml` and add:

```toml
[[ballsdex.packages]]
path = "packagemanager"
enabled = true
```

3. Set the `BALLSDEXBOT_EXTRA_TOML` environment variable if not already set:

```bash
export BALLSDEXBOT_EXTRA_TOML=/path/to/BallsDex-DiscordBot/config/extra.toml
```

4. Restart the bot:

```bash
python3 -m ballsdex
```

### Verify Installation

After restarting, you should see this in your bot logs:

```
Packages loaded: ..., packagemanager
```

The admin panel will now have a **Packages** section where you can manage all 3rd party packages.

## Usage

### Installing a New Package

1. Open the admin panel and navigate to **Packages**
2. Click **Install New Package** in the top-right corner
3. Enter the git repository URL (e.g., `https://github.com/user/repo.git`)
4. Optionally specify a version tag or branch
5. Click **Install Package**

The bot will automatically restart to load the new package.

### Managing Packages

In the **Packages** section, you can:

- **Enable/Disable**: Select packages and use the actions dropdown
- **Update**: Pull latest changes and reinstall
- **Uninstall**: Remove the package completely

### Actions

| Action | Description |
|--------|-------------|
| Enable | Enable a disabled package |
| Disable | Disable an enabled package |
| Uninstall | Remove the package completely (pip + files) |
| Update | Pull latest git changes and reinstall |

## Publishing Your Package

If you want to create a BallsDex package that can be installed via this package manager, follow the [official BallsDex package development guide](https://github.com/Ballsdex-Team/BallsDex-DiscordBot/blob/master/docs/dev/writing-custom-packages.md).

## License

MIT
