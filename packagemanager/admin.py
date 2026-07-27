from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin, messages
from django.db import models
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.safestring import mark_safe

from .models import InstalledPackage
from .services import (
    disable_package,
    enable_package,
    install_package,
    uninstall_package,
    update_package,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet


class InstallPackageForm(forms.Form):
    git_url = forms.URLField(
        label="Git Repository URL",
        help_text="Full URL to the git repository (e.g. https://github.com/user/repo.git)",
        widget=forms.URLInput(attrs={"size": 80}),
    )
    version_tag = forms.CharField(
        label="Version tag (optional)",
        help_text="Git tag or branch to pin. Leave empty for latest.",
        required=False,
        initial="",
    )


@admin.register(InstalledPackage)
class InstalledPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "app_path",
        "enabled_display",
        "installed_at",
        "actions_display",
    )
    list_filter = ("enabled",)
    readonly_fields = (
        "git_url",
        "name",
        "app_path",
        "dpy_package_path",
        "installed_at",
        "last_updated",
        "install_log",
    )
    search_fields = ("name", "app_path", "git_url")
    list_per_page = 50
    change_list_template = "admin/packagemanager/change_list.html"

    def get_urls(self) -> list[path]:
        custom_urls = [
            path(
                "install/",
                self.admin_site.admin_view(self.install_view),
                name="packagemanager_install",
            ),
        ]
        return custom_urls + super().get_urls()

    def install_view(self, request: HttpRequest):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can install packages.", messages.ERROR)
            return redirect("admin:packagemanager_installedpackage_changelist")

        if request.method == "POST":
            form = InstallPackageForm(request.POST)
            if form.is_valid():
                git_url = form.cleaned_data["git_url"]
                version_tag = form.cleaned_data["version_tag"]

                result = install_package(git_url, version_tag)

                if result["success"]:
                    self.message_user(
                        request,
                        f"Successfully installed package '{result['name']}'. "
                        f"App path: {result['app_path']}. "
                        f"The bot will restart automatically.",
                        messages.SUCCESS,
                    )
                    return redirect("admin:packagemanager_installedpackage_changelist")
                else:
                    self.message_user(
                        request,
                        f"Failed to install package: {result['error']}",
                        messages.ERROR,
                    )
        else:
            form = InstallPackageForm()

        context = {
            "form": form,
            "title": "Install New Package",
            "opts": self.model._meta,
            "has_permission": request.user.is_superuser,
        }
        return render(request, "admin/packagemanager/install_form.html", context)

    def enabled_display(self, obj: InstalledPackage) -> str:
        if self._is_core_package(obj):
            return mark_safe('<span style="color: #666; font-weight: bold;">Core</span>')
        if obj.enabled:
            return mark_safe('<span style="color: green; font-weight: bold;">Yes</span>')
        return mark_safe('<span style="color: red;">No</span>')

    enabled_display.short_description = "Enabled"

    def actions_display(self, obj: InstalledPackage) -> str:
        return mark_safe(
            '<span style="pointer-events: none; color: #999;">-</span>'
        )

    actions_display.short_description = "Actions"

    def get_actions(self, request: HttpRequest) -> dict:
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False 

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return request.user.is_superuser

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return request.user.is_superuser

    def save_model(self, request: HttpRequest, obj: InstalledPackage, form: forms.ModelForm, change: bool) -> None:
        if change:
            old = InstalledPackage.objects.get(pk=obj.pk)
            version_changed = old.version_tag != obj.version_tag
        else:
            version_changed = False

        super().save_model(request, obj, form, change)

        if version_changed:
            result = update_package(obj.pk)
            if result["success"]:
                self.message_user(
                    request,
                    f"Updated '{obj.name}' to version '{obj.version_tag or 'latest'}'. Bot will restart automatically.",
                    messages.SUCCESS,
                )
            else:
                self.message_user(request, f"{obj.name}: {result['error']}", messages.ERROR)

    def delete_model(self, request: HttpRequest, obj: InstalledPackage) -> None:
        result = uninstall_package(obj.id)
        if not result["success"]:
            self.message_user(request, f"{obj.name}: {result['error']}", messages.ERROR)

    def delete_queryset(self, request: HttpRequest, queryset: "QuerySet[InstalledPackage]") -> None:
        for pkg in queryset:
            result = uninstall_package(pkg.id)
            if not result["success"]:
                self.message_user(request, f"{pkg.name}: {result['error']}", messages.WARNING)

    actions = ("action_enable", "action_disable", "action_uninstall", "action_update")

    @staticmethod
    def _is_core_package(pkg: InstalledPackage) -> bool:
        """Return True if this package is the package manager itself (must not be disabled)."""
        return pkg.app_path == "packagemanager"

    @admin.action(description="Enable selected packages")
    def action_enable(self, request: HttpRequest, queryset: "QuerySet[InstalledPackage]"):
        count = 0
        for pkg in queryset:
            result = enable_package(pkg.id)
            if result["success"]:
                count += 1
            else:
                self.message_user(request, f"{pkg.name}: {result['error']}", messages.WARNING)
        if count:
            self.message_user(
                request,
                f"Enabled {count} package(s). Bot will restart automatically.",
                messages.SUCCESS,
            )

    @admin.action(description="Disable selected packages")
    def action_disable(self, request: HttpRequest, queryset: "QuerySet[InstalledPackage]"):
        count = 0
        for pkg in queryset:
            if self._is_core_package(pkg):
                self.message_user(
                    request,
                    f"{pkg.name}: cannot disable the package manager. Use Uninstall to remove it.",
                    messages.ERROR,
                )
                continue
            result = disable_package(pkg.id)
            if result["success"]:
                count += 1
            else:
                self.message_user(request, f"{pkg.name}: {result['error']}", messages.WARNING)
        if count:
            self.message_user(
                request,
                f"Disabled {count} package(s). Bot will restart automatically.",
                messages.SUCCESS,
            )

    @admin.action(description="Uninstall selected packages")
    def action_uninstall(self, request: HttpRequest, queryset: "QuerySet[InstalledPackage]"):
        core_count = queryset.filter(app_path="packagemanager").count()
        if core_count:
            self.message_user(
                request,
                "WARNING: You are about to uninstall the Package Manager itself. "
                "The bot will lose all package management capabilities until it is reinstalled manually.",
                messages.WARNING,
            )
        count = 0
        for pkg in queryset:
            result = uninstall_package(pkg.id)
            if result["success"]:
                count += 1
            else:
                self.message_user(request, f"{pkg.name}: {result['error']}", messages.WARNING)
        if count:
            self.message_user(
                request,
                f"Uninstalled {count} package(s). Bot will restart automatically.",
                messages.SUCCESS,
            )

    @admin.action(description="Update selected packages (git pull + reinstall)")
    def action_update(self, request: HttpRequest, queryset: "QuerySet[InstalledPackage]"):
        count = 0
        for pkg in queryset:
            result = update_package(pkg.id)
            if result["success"]:
                count += 1
            else:
                self.message_user(request, f"{pkg.name}: {result['error']}", messages.WARNING)
        if count:
            self.message_user(
                request,
                f"Updated {count} package(s). Bot will restart automatically.",
                messages.SUCCESS,
            )
