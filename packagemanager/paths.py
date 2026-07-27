import os
import pathlib


def get_extra_dir() -> pathlib.Path:
    """Return the path to the extra/ directory, resolving for both Docker and Dockerless."""
    extra_dir = os.environ.get("BALLSDEXBOT_EXTRA_DIR")
    if extra_dir:
        p = pathlib.Path(extra_dir)
        if p.exists():
            return p

    extra_toml = os.environ.get("BALLSDEXBOT_EXTRA_TOML")
    if extra_toml:
        toml_path = pathlib.Path(extra_toml)
        if toml_path.exists():
            project_root = toml_path.resolve().parent.parent
            extra = project_root / "extra"
            if extra.exists():
                return extra

    base = pathlib.Path(__file__).resolve().parent.parent.parent
    for candidate in [base, base.parent]:
        if (candidate / "admin_panel").exists() and (candidate / "extra").exists():
            return candidate / "extra"

    extra = base / "extra"
    if extra.exists():
        return extra
    return base.parent / "extra"


EXTRA_DIR = get_extra_dir()
RESTART_FLAG = EXTRA_DIR.parent / "config" / ".restart_needed"
