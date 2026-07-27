from django.db import models


class InstalledPackage(models.Model):
    git_url = models.URLField(
        help_text="Git repository URL of the package",
        unique=True,
    )
    name = models.CharField(
        max_length=128,
        help_text="Display name of the package (auto-extracted from repo)",
    )
    app_path = models.CharField(
        max_length=128,
        help_text="Django import path of the app (e.g. 'collector')",
    )
    dpy_package_path = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="Discord.py cog extension path (e.g. 'collector.package')",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this package is currently enabled",
    )
    is_legacy = models.BooleanField(
        default=False,
        help_text="Imported from config/extra.toml, not managed by this panel",
    )
    installed_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    version_tag = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Optional git tag or branch to pin (leave empty for latest)",
    )
    install_log = models.TextField(
        blank=True,
        default="",
        help_text="Output from the last install/update operation",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Installed Package"
        verbose_name_plural = "Installed Packages"

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.name} ({status})"
