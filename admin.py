# -*- coding: utf-8 -*-
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
from models import Group
from models import Content
from models import Mail


class GroupAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', )
    ordering = ('name', )
    prepopulated_fields = {"slug": ("name",)}

admin.site.register(Group, GroupAdmin)

class ContentAdmin(admin.ModelAdmin):
    search_fields = ('title', 'caption', 'mimetype', 'caption')
    list_display = ('title',  'caption', 'mimetype', 'filesize', 'created', 'updated')
    ordering = ('title',)

admin.site.register(Content, ContentAdmin)

class MailAdmin(admin.ModelAdmin):
    search_fields = ('id', 'status',)
    list_display = ('id', 'status',  'filesize', 'created',)
    ordering = ('created',)

admin.site.register(Mail, MailAdmin)
