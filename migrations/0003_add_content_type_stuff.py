# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import content.models
import django.core.files.storage


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('content', '0002_content_point_geom'),
    ]

    operations = [
        migrations.AddField(
            model_name='content',
            name='content_type',
            field=models.ForeignKey(default=None, to='contenttypes.ContentType'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='content',
            name='object_id',
            field=models.PositiveIntegerField(default=None),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='audioinstance',
            name='file',
            field=models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'audio'), editable=False),
        ),
        migrations.AlterField(
            model_name='content',
            name='file',
            field=models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'content'), editable=False),
        ),
        migrations.AlterField(
            model_name='content',
            name='peers',
            field=models.ManyToManyField(related_name='_peers_+', editable=False, to='content.Content', blank=True),
        ),
        migrations.AlterField(
            model_name='content',
            name='preview',
            field=models.ImageField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'preview'), editable=False, blank=True),
        ),
        migrations.AlterField(
            model_name='image',
            name='thumbnail',
            field=models.ImageField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'preview'), editable=False),
        ),
        migrations.AlterField(
            model_name='mail',
            name='file',
            field=models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'/Users/arista/Documents/workspace/Djangos/SensDB/sensdb/var/mail/content'), editable=False),
        ),
        migrations.AlterField(
            model_name='video',
            name='thumbnail',
            field=models.ImageField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'preview'), editable=False),
        ),
        migrations.AlterField(
            model_name='videoinstance',
            name='file',
            field=models.FileField(upload_to=content.models.upload_split_by_1000, storage=django.core.files.storage.FileSystemStorage(location=b'video'), editable=False),
        ),
    ]
