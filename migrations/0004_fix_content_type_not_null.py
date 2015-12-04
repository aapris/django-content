# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import content.models
import django.core.files.storage


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0003_add_content_type_stuff'),
    ]

    operations = [
        migrations.AlterField(
            model_name='content',
            name='content_type',
            field=models.ForeignKey(blank=True, to='contenttypes.ContentType', null=True),
        ),
        migrations.AlterField(
            model_name='content',
            name='object_id',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
    ]
