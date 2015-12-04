# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import content.models
import django.contrib.gis.db.models.fields
import django.core.files.storage
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Audioinstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mimetype', models.CharField(max_length=200, editable=False)),
                ('filesize', models.IntegerField(null=True, editable=False, blank=True)),
                ('duration', models.FloatField(null=True, editable=False, blank=True)),
                ('bitrate', models.FloatField(null=True, editable=False, blank=True)),
                ('extension', models.CharField(max_length=16, editable=False)),
                ('file', models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'audio'), editable=False)),
                ('command', models.CharField(max_length=2000, editable=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Content',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(default=b'UNPROCESSED', max_length=40, editable=False)),
                ('privacy', models.CharField(default=b'PRIVATE', max_length=40, verbose_name='Privacy', choices=[(b'PRIVATE', 'Private'), (b'RESTRICTED', 'Group'), (b'PUBLIC', 'Public')])),
                ('uid', models.CharField(default=content.models.get_uid, unique=True, max_length=40, editable=False, db_index=True)),
                ('originalfilename', models.CharField(verbose_name='Original file name', max_length=256, null=True, editable=False)),
                ('filesize', models.IntegerField(null=True, editable=False)),
                ('filetime', models.DateTimeField(null=True, editable=False, blank=True)),
                ('mimetype', models.CharField(max_length=200, null=True, editable=False)),
                ('file', models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'content'), editable=False)),
                ('preview', models.ImageField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'preview'), editable=False, blank=True)),
                ('md5', models.CharField(max_length=32, null=True, editable=False)),
                ('sha1', models.CharField(max_length=40, null=True, editable=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('opens', models.DateTimeField(null=True, blank=True)),
                ('expires', models.DateTimeField(null=True, blank=True)),
                ('title', models.CharField(max_length=200, verbose_name='Title', blank=True)),
                ('caption', models.TextField(verbose_name='Caption', blank=True)),
                ('author', models.CharField(max_length=200, verbose_name='Author', blank=True)),
                ('keywords', models.CharField(max_length=500, verbose_name='Keywords', blank=True)),
                ('place', models.CharField(max_length=500, verbose_name='Place', blank=True)),
                ('linktype', models.CharField(max_length=500, blank=True)),
                ('point', django.contrib.gis.db.models.fields.PointField(srid=4326, null=True, geography=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100)),
                ('description', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('users', models.ManyToManyField(related_name='contentgroups', to=settings.AUTH_USER_MODEL, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Mail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(default=b'UNPROCESSED', max_length=40, choices=[(b'UNPROCESSED', b'UNPROCESSED'), (b'PROCESSED', b'PROCESSED'), (b'DUPLICATE', b'DUPLICATE'), (b'FAILED', b'FAILED')])),
                ('filesize', models.IntegerField(null=True, editable=False)),
                ('file', models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'/Users/arista/Documents/workspace/Djangos/SensDB/sensdb/var/mail/content'), editable=False)),
                ('md5', models.CharField(max_length=32, editable=False, db_index=True)),
                ('sha1', models.CharField(max_length=40, editable=False, db_index=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('processed', models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Videoinstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mimetype', models.CharField(max_length=200, editable=False)),
                ('filesize', models.IntegerField(null=True, editable=False, blank=True)),
                ('duration', models.FloatField(null=True, editable=False, blank=True)),
                ('bitrate', models.FloatField(null=True, editable=False, blank=True)),
                ('extension', models.CharField(max_length=16, editable=False)),
                ('width', models.IntegerField(null=True, editable=False, blank=True)),
                ('height', models.IntegerField(null=True, editable=False, blank=True)),
                ('framerate', models.FloatField(null=True, editable=False, blank=True)),
                ('file', models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'video'), editable=False)),
                ('command', models.CharField(max_length=2000, editable=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Audio',
            fields=[
                ('content', models.OneToOneField(primary_key=True, serialize=False, to='content.Content')),
                ('duration', models.FloatField(null=True, blank=True)),
                ('bitrate', models.FloatField(null=True, editable=False, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('content', models.OneToOneField(primary_key=True, serialize=False, editable=False, to='content.Content')),
                ('width', models.IntegerField(null=True, editable=False, blank=True)),
                ('height', models.IntegerField(null=True, editable=False, blank=True)),
                ('rotate', models.IntegerField(default=0, null=True, blank=True, choices=[(0, 0), (90, 90), (180, 180), (270, 270)])),
                ('thumbnail', models.ImageField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'preview'), editable=False)),
            ],
        ),
        migrations.CreateModel(
            name='Uploadinfo',
            fields=[
                ('content', models.OneToOneField(primary_key=True, serialize=False, editable=False, to='content.Content')),
                ('sessionid', models.CharField(max_length=200, editable=False, blank=True)),
                ('ip', models.GenericIPAddressField(null=True, editable=False, blank=True)),
                ('useragent', models.CharField(max_length=500, editable=False, blank=True)),
                ('info', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('content', models.OneToOneField(primary_key=True, serialize=False, editable=False, to='content.Content')),
                ('width', models.IntegerField(null=True, editable=False, blank=True)),
                ('height', models.IntegerField(null=True, editable=False, blank=True)),
                ('duration', models.FloatField(null=True, editable=False, blank=True)),
                ('bitrate', models.CharField(max_length=256, null=True, editable=False, blank=True)),
                ('thumbnail', models.ImageField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'preview'), editable=False)),
            ],
        ),
        migrations.AddField(
            model_name='videoinstance',
            name='content',
            field=models.ForeignKey(related_name='videoinstances', editable=False, to='content.Content'),
        ),
        migrations.AddField(
            model_name='content',
            name='group',
            field=models.ForeignKey(blank=True, to='content.Group', null=True),
        ),
        migrations.AddField(
            model_name='content',
            name='parent',
            field=models.ForeignKey(blank=True, editable=False, to='content.Content', null=True),
        ),
        migrations.AddField(
            model_name='content',
            name='peers',
            field=models.ManyToManyField(related_name='_content_peers_+', editable=False, to='content.Content', blank=True),
        ),
        migrations.AddField(
            model_name='content',
            name='user',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='audioinstance',
            name='content',
            field=models.ForeignKey(related_name='audioinstances', editable=False, to='content.Content'),
        ),
    ]
