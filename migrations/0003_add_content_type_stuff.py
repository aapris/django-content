# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('content', '0002_content_point_geom'),
    ]

    operations = [
        migrations.AddField(
            model_name='content',
            name='content_type',
            field=models.ForeignKey(default=None, blank=True, to='contenttypes.ContentType', null=True),
        ),
        migrations.AddField(
            model_name='content',
            name='object_id',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='content',
            name='peers',
            field=models.ManyToManyField(related_name='_content_peers_+', editable=False, to='content.Content', blank=True),
        ),
    ]
