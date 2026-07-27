import os
import pathlib


def get_extra_dir() -> pathlib.Path:
    """Return the path to the extra/ directory, resolving for both Docker and Dockerless."""
    base = pathlib.Path(__file__).resolve().parent.parent.parent
    extra = base / "extra"
    if extra.exists():
        return extra
    extra = base.parent / "extra"
    if extra.exists():
        return extra
    return base / "extra"


EXTRA_DIR = get_extra_dir()
RESTART_FLAG = EXTRA_DIR.parent / "config" / ".restart_needed"
