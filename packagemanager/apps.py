import logging
import threading

from django.apps import AppConfig

log = logging.getLogger("packagemanager")


class PackagemanagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "packagemanager"
    verbose_name = "Package Manager"
    dpy_package = "packagemanager.package"

    def ready(self) -> None:
        # Run legacy import in a background thread to avoid SynchronousOnlyOperation
        # when ready() is called from an async context (e.g. settings app).
        thread = threading.Thread(target=self._import_legacy, daemon=True)
        thread.start()

    def _import_legacy(self) -> None:
        try:
            from .services import import_legacy_packages

            count = import_legacy_packages()
            if count:
                log.info("Imported %d package(s) from extra.toml", count)
        except Exception:
            log.exception("Failed to import legacy packages")
