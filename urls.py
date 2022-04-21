"""
Provide urlpatterns for original content file, preview and instances.
"""
from django.urls import path, re_path

from content import views

urlpatterns = [
    path("original/<str:uid>/<str:filename>", views.original, name="original"),
    path("instance/<str:uid>.<str:extension>", views.instance, name="instance"),
    re_path(
        r"preview/(?P<uid>\w+)-(?P<width>(\d+|%d))x(?P<height>(\d+|%d))(?P<action>-\w+)?\.(?P<ext>\w+)$",
        views.preview,
        name="preview",
    ),
]
