import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="InstalledPackage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "git_url",
                    models.URLField(
                        help_text="Git repository URL of the package",
                        unique=True,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display name of the package (auto-extracted from repo)",
                        max_length=128,
                    ),
                ),
                (
                    "app_path",
                    models.CharField(
                        help_text="Django import path of the app (e.g. 'collector')",
                        max_length=128,
                    ),
                ),
                (
                    "dpy_package_path",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Discord.py cog extension path (e.g. 'collector.package')",
                        max_length=256,
                    ),
                ),
                (
                    "enabled",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this package is currently enabled",
                    ),
                ),
                (
                    "is_legacy",
                    models.BooleanField(
                        default=False,
                        help_text="Imported from config/extra.toml, not managed by this panel",
                    ),
                ),
                (
                    "installed_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "last_updated",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "version_tag",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Optional git tag or branch to pin (leave empty for latest)",
                        max_length=128,
                    ),
                ),
                (
                    "install_log",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Output from the last install/update operation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Installed Package",
                "verbose_name_plural": "Installed Packages",
                "ordering": ["name"],
            },
        ),
    ]
