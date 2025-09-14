"""
Content's admin definitions.

You can override these in your own application's admin.py, just do this:

from models import Content
admin.site.unregister(Content)
class ContentAdmin(admin.ModelAdmin):
    # your model admin definitions here

admin.site.register(Content, ContentAdmin)
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Content, Group, Mail


class GroupAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Content Groups."""

    list_display = ["name", "slug", "description", "users_count", "created"]
    list_filter = ["created"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["users"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "slug", "description")}),
        ("Users", {"fields": ("users",)}),
        ("Timestamps", {"fields": ("created", "updated"), "classes": ("collapse",)}),
    )

    readonly_fields = ["created", "updated"]
    ordering = ["name"]

    def users_count(self, obj):
        """Display count of users in group."""
        count = obj.users.count()
        if count > 0:
            return format_html("<strong>{}</strong>", count)
        return count

    users_count.short_description = "Users"
    users_count.admin_order_field = "users__count"


admin.site.register(Group, GroupAdmin)


class ContentAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Content model to enable easy file uploads."""

    # Display configuration
    list_display = ["uid", "originalfilename", "title", "mimetype", "filesize_kb", "privacy", "created"]
    list_filter = ["privacy", "mimetype", "created", "group", "user"]
    search_fields = ["originalfilename", "title", "caption", "keywords", "uid"]

    # Form organization
    fieldsets = (
        (
            "File Upload",
            {
                "fields": ("file",),
                "description": "Upload a new file. Metadata will be automatically extracted.",
            },
        ),
        ("Basic Information", {"fields": ("title", "caption", "author", "keywords")}),
        ("Access Control", {"fields": ("privacy", "user", "group")}),
        ("Location", {"fields": ("place", "point")}),
        (
            "File Information",
            {
                "fields": ("originalfilename", "filesize", "mimetype", "md5", "sha1", "filetime"),
                "classes": ("collapse",),
                "description": "Automatically populated file metadata.",
            },
        ),
        ("Timestamps", {"fields": ("created",), "classes": ("collapse",)}),
    )

    # Form behavior
    readonly_fields = [
        "uid",
        "originalfilename",
        "filesize",
        "mimetype",
        "md5",
        "sha1",
        "filetime",
        "created",
        "status",
    ]
    autocomplete_fields = ["user", "group"]

    # Ordering and pagination
    ordering = ["-created"]
    list_per_page = 50

    def filesize_kb(self, obj):
        """Display file size in KB/MB for better readability."""
        if obj.filesize:
            if obj.filesize < 1024 * 1024:  # Less than 1MB
                return f"{obj.filesize / 1024:.1f} KB"
            else:
                return f"{obj.filesize / (1024 * 1024):.1f} MB"
        return "-"

    filesize_kb.short_description = "File Size"
    filesize_kb.admin_order_field = "filesize"


admin.site.register(Content, ContentAdmin)


class MailAdmin(admin.ModelAdmin):
    search_fields = ("id", "status")
    list_display = ("id", "status", "filesize", "created")
    ordering = ("-created",)


admin.site.register(Mail, MailAdmin)
