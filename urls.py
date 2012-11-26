# -*- coding: utf-8 -*-

from django.conf.urls import patterns, include, url
#from django.conf import settings

import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^search/$', views.search, name='search'),
    url(r'^upload/$', views.upload, name='upload'),
    url(r'^html5upload/$', views.html5upload, name='html5upload'),
    url(r'^edit/(?P<uid>[\w]+)/$', views.edit, name='edit'),
    url(r'^instance/(?P<uid>[\w]+)-(?P<width>\d+)x(?P<height>\d+)(?P<action>\-\w+)?\.(?P<ext>\w+)$', views.instance, name='instance'),
    url(r'^view/(?P<uid>[\w]+)-(?P<width>(\d+|%d))x(?P<height>(\d+|%d))(?P<action>\-\w+)?\.(?P<ext>\w+)$', views.view, name='view'),
    url(r'^foobar/(?P<uid>[\w]+)-(?P<id>[\d]+)\.(?P<ext>\w+)$', views.foobar, name='foobar'),
    url(r'^original/(?P<uid>[\w]+)/(?P<filename>.+)$', views.original, name='original'),
    url(r'^original/(?P<uid>[\w]+)$', views.original, name='original'),
    url(r'^metadata/(\w+)$', views.metadata, name='metadata'),
)


from content.apitastypie import ContentResource
from content.apitastypie import UserResource
from tastypie.api import Api

v1_api = Api(api_name='v1')
v1_api.register(ContentResource())
v1_api.register(UserResource())

urlpatterns += patterns('',
    url(r'^api/v1/content/upload/?$', views.api_upload, name='api_upload'),
    (r'^api/', include(v1_api.urls)),
)
