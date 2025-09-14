"""
Content's admin definitions.

You can override these in your own application's admin.py, just do this:

from models import Content
admin.site.unregister(Content)
class ContentAdmin(admin.ModelAdmin):
    # your model admin definitions here

admin.site.register(Content, ContentAdmin)
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Content, Group


class ContentAdminForm(forms.ModelForm):
    """Custom form for Content admin to handle original filename extraction."""

    class Meta:
        model = Content
        fields = [
            # Only include editable fields
            "privacy",
            "user",
            "group",
            "file",
            "linktype",
            "point",
            "point_geom",
            "title",
            "caption",
            "author",
            "keywords",
            "place",
            "opens",
            "expires",
            "content_type",
            "object_id",
        ]

    def save(self, commit=True):
        """Override save to extract original filename from uploaded file."""
        instance = super().save(commit=False)

        # Extract original filename from uploaded file if available
        if "file" in self.changed_data and self.cleaned_data.get("file"):
            uploaded_file = self.cleaned_data["file"]
            if hasattr(uploaded_file, "name") and uploaded_file.name:
                # Store the original filename before Django processes it
                instance.original_filename = uploaded_file.name

        if commit:
            instance.save()
        return instance


class GroupAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Content Groups."""

    list_display = ["name", "slug", "description", "users_count", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["users"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "slug", "description")}),
        ("Users", {"fields": ("users",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    readonly_fields = ["created_at", "updated_at"]
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

    # Use custom form
    form = ContentAdminForm

    # Display configuration
    list_display = ["uid", "original_filename", "title", "mimetype", "filesize_kb", "privacy", "created_at"]
    list_filter = ["privacy", "mimetype", "created_at", "group", "user"]
    search_fields = ["original_filename", "title", "caption", "keywords", "uid"]

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
                "fields": ("original_filename", "file_size", "mimetype", "sha1", "filetime"),
                "classes": ("collapse",),
                "description": "Automatically populated file metadata.",
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    # Form behavior
    readonly_fields = [
        "uid",
        "original_filename",
        "file_size",
        "mimetype",
        "sha1",
        "filetime",
        "created_at",
        "status",
    ]
    autocomplete_fields = ["user", "group"]

    # Ordering and pagination
    ordering = ["-created_at"]
    list_per_page = 50

    def filesize_kb(self, obj):
        """Display file size in KB/MB for better readability."""
        if obj.file_size:
            if obj.file_size < 1024 * 1024:  # Less than 1MB
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "-"

    filesize_kb.short_description = "File Size"
    filesize_kb.admin_order_field = "file_size"


admin.site.register(Content, ContentAdmin)
