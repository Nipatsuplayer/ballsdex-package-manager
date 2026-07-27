from __future__ import annotations

import ast
import logging
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from .paths import EXTRA_DIR, RESTART_FLAG

log = logging.getLogger("packagemanager")


def _find_uv() -> str | None:
    """Find the uv binary, return path or None."""
    return shutil.which("uv")


def _run_pip(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run pip install/uninstall via uv or fallback to pip."""
    uv = _find_uv()
    if uv:
        cmd = [uv, "pip"] + args
    else:
        cmd = [sys.executable, "-m", "pip"] + args

    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=300,
    )
    output = result.stdout + "\n" + result.stderr
    return result.returncode, output.strip()


def _run_git(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a git command."""
    cmd = ["git"] + args
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=120,
    )
    output = result.stdout + "\n" + result.stderr
    return result.returncode, output.strip()


def _run_manage_py(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a Django manage.py command."""
    if cwd is None:
        cwd = str(EXTRA_DIR.parent / "admin_panel")
    manage_py = os.path.join(cwd, "manage.py")
    if not os.path.exists(manage_py):
        return 1, f"manage.py not found at {manage_py}"

    cmd = [sys.executable, manage_py] + args
    log.info("Running: %s", " ".join(cmd))

    env = os.environ.copy()
    toml_path = _get_extra_toml_path()
    if toml_path:
        env["BALLSDEXBOT_EXTRA_TOML"] = str(toml_path)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=120,
    )
    output = result.stdout + "\n" + result.stderr
    return result.returncode, output.strip()


def _repo_name_from_url(git_url: str) -> str:
    """Extract a directory name from a git URL."""
    name = git_url.rstrip("/").rsplit("/", 1)[-1]
    name = name.rsplit(".git", 1)[0]
    name = re.sub(r"[^a-zA-Z0-9_\-.]", "_", name)
    return name


def _get_extra_toml_path() -> Path | None:
    """Get the path to config/extra.toml."""
    extra_toml = os.environ.get("BALLSDEXBOT_EXTRA_TOML")
    if extra_toml:
        return Path(extra_toml)
    # Try to find it relative to the project root
    config_path = EXTRA_DIR.parent / "config" / "extra.toml"
    if config_path.exists():
        return config_path
    return None


def _read_extra_toml() -> dict:
    """Read the extra.toml file and return its contents as a dict."""
    path = _get_extra_toml_path()
    if not path or not path.exists():
        return {"ballsdex": {"packages": []}}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {"ballsdex": {"packages": []}}


def _write_extra_toml(contents: dict) -> None:
    """Write contents to extra.toml in TOML format."""
    path = _get_extra_toml_path()
    if not path:
        # Create config/extra.toml if it doesn't exist
        config_dir = EXTRA_DIR.parent / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "extra.toml"

    packages = contents.get("ballsdex", {}).get("packages", [])

    lines = ["# This file is managed by the Package Manager plugin."]
    lines.append("# Manual edits are allowed but not recommended.")
    lines.append("")

    for pkg in packages:
        lines.append("[[ballsdex.packages]]")
        if pkg.get("location"):
            lines.append(f'location = "{pkg["location"]}"')
        lines.append(f'path = "{pkg["path"]}"')
        lines.append(f'enabled = {str(pkg.get("enabled", True)).lower()}')
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Written extra.toml with %d package(s)", len(packages))


def _add_to_extra_toml(
    app_path: str,
    location: str = "",
    enabled: bool = True,
) -> None:
    """Add a package entry to extra.toml."""
    contents = _read_extra_toml()
    packages = contents.setdefault("ballsdex", {}).setdefault("packages", [])

    # Check if already exists
    for pkg in packages:
        if pkg.get("path") == app_path:
            pkg["enabled"] = enabled
            if location:
                pkg["location"] = location
            _write_extra_toml(contents)
            return

    # Add new entry
    packages.append({
        "location": location,
        "path": app_path,
        "enabled": enabled,
    })
    _write_extra_toml(contents)


def _remove_from_extra_toml(app_path: str) -> None:
    """Remove a package entry from extra.toml."""
    contents = _read_extra_toml()
    packages = contents.get("ballsdex", {}).get("packages", [])
    packages = [p for p in packages if p.get("path") != app_path]
    contents["ballsdex"]["packages"] = packages
    _write_extra_toml(contents)


def _toggle_extra_toml(app_path: str, enabled: bool) -> None:
    """Toggle enabled state in extra.toml."""
    contents = _read_extra_toml()
    packages = contents.get("ballsdex", {}).get("packages", [])
    for pkg in packages:
        if pkg.get("path") == app_path:
            pkg["enabled"] = enabled
            break
    _write_extra_toml(contents)


def discover_package_apps(repo_path: Path) -> list[dict[str, str]]:
    """Scan a repo for Django apps with dpy_package attribute.

    Returns a list of dicts with keys: app_path, dpy_package_path, name
    """
    apps_found: list[dict[str, str]] = []

    for apps_py in repo_path.rglob("apps.py"):
        try:
            content = apps_py.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            has_appconfig_base = False
            for base in node.bases:
                base_name = ""
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if "AppConfig" in base_name:
                    has_appconfig_base = True
                    break

            if not has_appconfig_base:
                continue

            app_name = ""
            dpy_package = ""
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "name" and isinstance(item.value, ast.Constant):
                                app_name = item.value.value
                            elif target.id == "dpy_package" and isinstance(item.value, ast.Constant):
                                dpy_package = item.value.value

            if app_name:
                app_path = app_name.split(".")[-1]
                apps_found.append({
                    "app_path": app_path,
                    "app_name": app_name,
                    "dpy_package_path": dpy_package,
                    "name": app_path.replace("_", " ").title(),
                })

    return apps_found


def install_package(git_url: str, version_tag: str = "") -> dict:
    """Install a package from a git repository.

    Returns a dict with success status, error message, and metadata.
    """
    result: dict = {"success": False, "error": "", "name": "", "app_path": "", "dpy_package_path": "", "log": ""}

    if not git_url.endswith(".git"):
        git_url = git_url + ".git"

    version_tag = version_tag.lstrip("@").strip() if version_tag else ""

    repo_name = _repo_name_from_url(git_url)
    clone_dir = EXTRA_DIR / repo_name

    from .models import InstalledPackage

    if InstalledPackage.objects.filter(git_url=git_url).exists():
        result["error"] = "A package from this URL is already installed."
        return result

    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    clone_args = ["clone", git_url, str(clone_dir)]
    if version_tag:
        clone_args = ["clone", "--branch", version_tag, "--depth", "1", git_url, str(clone_dir)]

    rc, output = _run_git(clone_args)
    if rc != 0:
        result["error"] = f"Failed to clone repository:\n{output}"
        result["log"] = output
        return result

    apps = discover_package_apps(clone_dir)
    if not apps:
        shutil.rmtree(clone_dir)
        result["error"] = "No Django AppConfig with dpy_package found in this repository."
        return result

    app = apps[0]
    result["name"] = app["name"]
    result["app_path"] = app["app_path"]
    result["dpy_package_path"] = app["dpy_package_path"]

    pip_args = ["install", str(clone_dir)]
    rc, pip_output = _run_pip(pip_args)
    result["log"] = pip_output

    if rc != 0:
        shutil.rmtree(clone_dir)
        result["error"] = f"pip install failed:\n{pip_output}"
        return result

    _add_to_extra_toml(
        app_path=result["app_path"],
        location=git_url,
        enabled=True,
    )

    rc, migrate_output = _run_manage_py(["migrate", result["app_path"]])
    result["log"] += f"\n{migrate_output}"
    if rc != 0:
        migrate_cmd = f"cd {EXTRA_DIR.parent / 'admin_panel'} && python manage.py migrate {result['app_path']}"
        log.warning(
            "Auto-migrate failed. Run this command after restart:\n  %s\nOutput: %s",
            migrate_cmd,
            migrate_output,
        )
        result["log"] += f"\n\nMigrations could not be applied automatically. After restart, run:\n  {migrate_cmd}"
    else:
        log.info("Migrations applied successfully for %s", result["app_path"])

    try:
        InstalledPackage.objects.update_or_create(
            git_url=git_url,
            defaults={
                "name": result["name"],
                "app_path": result["app_path"],
                "dpy_package_path": result["dpy_package_path"],
                "version_tag": version_tag,
                "install_log": pip_output,
                "enabled": True,
            },
        )
    except Exception as e:
        log.warning("Failed to save to database: %s", e)

    _write_restart_flag(f"Installed package: {result['name']}")
    result["success"] = True
    return result


def uninstall_package(package_id: int) -> dict:
    """Uninstall a package by its database ID."""
    from .models import InstalledPackage

    result: dict = {"success": False, "error": ""}

    try:
        pkg = InstalledPackage.objects.get(id=package_id)
    except InstalledPackage.DoesNotExist:
        result["error"] = "Package not found."
        return result

    rc, output = _run_pip(["uninstall", pkg.app_path, "-y"])
    if rc != 0:
        result["error"] = f"pip uninstall failed:\n{output}"
        return result

    repo_name = _repo_name_from_url(pkg.git_url)
    clone_dir = EXTRA_DIR / repo_name
    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    _remove_from_extra_toml(pkg.app_path)

    pkg_name = pkg.name
    pkg.delete()

    _write_restart_flag(f"Uninstalled package: {pkg_name}")
    result["success"] = True
    return result


def enable_package(package_id: int) -> dict:
    """Enable a package."""
    from .models import InstalledPackage

    result: dict = {"success": False, "error": ""}
    try:
        pkg = InstalledPackage.objects.get(id=package_id)
    except InstalledPackage.DoesNotExist:
        result["error"] = "Package not found."
        return result

    if pkg.enabled:
        result["error"] = "Package is already enabled."
        return result

    pkg.enabled = True
    pkg.save(update_fields=["enabled", "last_updated"])

    _toggle_extra_toml(pkg.app_path, enabled=True)

    _write_restart_flag(f"Enabled package: {pkg.name}")
    result["success"] = True
    return result


def disable_package(package_id: int) -> dict:
    """Disable a package."""
    from .models import InstalledPackage

    result: dict = {"success": False, "error": ""}
    try:
        pkg = InstalledPackage.objects.get(id=package_id)
    except InstalledPackage.DoesNotExist:
        result["error"] = "Package not found."
        return result

    if not pkg.enabled:
        result["error"] = "Package is already disabled."
        return result

    pkg.enabled = False
    pkg.save(update_fields=["enabled", "last_updated"])

    _toggle_extra_toml(pkg.app_path, enabled=False)

    _write_restart_flag(f"Disabled package: {pkg.name}")
    result["success"] = True
    return result


def update_package(package_id: int) -> dict:
    """Update a package by pulling latest changes and reinstalling."""
    from .models import InstalledPackage

    result: dict = {"success": False, "error": "", "log": ""}

    try:
        pkg = InstalledPackage.objects.get(id=package_id)
    except InstalledPackage.DoesNotExist:
        result["error"] = "Package not found."
        return result

    repo_name = _repo_name_from_url(pkg.git_url)
    clone_dir = EXTRA_DIR / repo_name

    if not clone_dir.exists():
        result["error"] = "Package directory not found. Try reinstalling."
        return result

    tag = pkg.version_tag.lstrip("@").strip() if pkg.version_tag else ""

    if tag:
        rc, output = _run_git(["fetch", "--all", "--tags"], cwd=str(clone_dir))
        if rc != 0:
            result["error"] = f"git fetch failed:\n{output}"
            result["log"] = output
            return result

        rc, output = _run_git(["checkout", tag], cwd=str(clone_dir))
        if rc != 0:
            result["error"] = f"Could not checkout version '{tag}':\n{output}"
            result["log"] = output
            return result
    else:
        rc, output = _run_git(["pull"], cwd=str(clone_dir))
        if rc != 0:
            result["error"] = f"git pull failed:\n{output}"
            result["log"] = output
            return result

    rc, pip_output = _run_pip(["install", str(clone_dir)])
    result["log"] = output + "\n" + pip_output

    if rc != 0:
        result["error"] = f"pip install failed:\n{pip_output}"
        return result

    apps = discover_package_apps(clone_dir)
    if apps:
        app = apps[0]
        pkg.app_path = app["app_path"]
        pkg.dpy_package_path = app["dpy_package_path"]
        pkg.name = app["name"]

    _add_to_extra_toml(
        app_path=pkg.app_path,
        location=pkg.git_url,
        enabled=pkg.enabled,
    )

    rc, migrate_output = _run_manage_py(["migrate", pkg.app_path])
    result["log"] += f"\n{migrate_output}"
    if rc != 0:
        migrate_cmd = f"cd {EXTRA_DIR.parent / 'admin_panel'} && python manage.py migrate {pkg.app_path}"
        log.warning(
            "Auto-migrate failed. Run this command after restart:\n  %s\nOutput: %s",
            migrate_cmd,
            migrate_output,
        )
        result["log"] += f"\n\nMigrations could not be applied automatically. After restart, run:\n  {migrate_cmd}"
    else:
        log.info("Migrations applied successfully for %s", pkg.app_path)

    pkg.install_log = result["log"]
    pkg.save()

    _write_restart_flag(f"Updated package: {pkg.name}")
    result["success"] = True
    return result


def _write_restart_flag(reason: str = "") -> None:
    """Write the restart flag file."""
    try:
        RESTART_FLAG.parent.mkdir(parents=True, exist_ok=True)
        RESTART_FLAG.write_text(reason, encoding="utf-8")
        log.info("Restart flag written: %s", reason)
    except Exception:
        log.exception("Failed to write restart flag")


def import_packages_from_extra_toml() -> int:
    """Sync packages from config/extra.toml into the database.

    Creates InstalledPackage records for any extra.toml entries not yet in the DB.

    Returns the number of new records created.
    """
    from .models import InstalledPackage

    path = _get_extra_toml_path()
    if not path or not path.exists():
        return 0

    try:
        with open(path, "rb") as f:
            contents = tomllib.load(f)
    except Exception:
        return 0

    packages = contents.get("ballsdex", {}).get("packages", [])
    created = 0

    for entry in packages:
        app_path = entry.get("path", "")
        if not app_path:
            continue

        if InstalledPackage.objects.filter(app_path=app_path).exists():
            continue

        git_url = entry.get("location", "")
        enabled = entry.get("enabled", True)

        dpy_package = ""
        name = app_path.replace("_", " ").title()
        try:
            from django.apps import apps as django_apps

            for app_config in django_apps.get_app_configs():
                if getattr(app_config, "label", "") == app_path:
                    dpy_package = getattr(app_config, "dpy_package", "")
                    name = getattr(app_config, "verbose_name", name)
                    break
        except Exception:
            pass

        InstalledPackage.objects.create(
            git_url=git_url or f"file://{app_path}",
            name=name,
            app_path=app_path,
            dpy_package_path=dpy_package,
            enabled=enabled,
        )
        created += 1
        log.info("Imported package from extra.toml: %s", app_path)

    return created
