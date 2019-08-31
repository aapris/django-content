# Generated by Django 2.2.4 on 2019-08-31 12:29

import content.models
import django.core.files.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0003_add_content_type_stuff'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audioinstance',
            name='file',
            field=models.FileField(editable=False, storage=django.core.files.storage.FileSystemStorage(location='audio'), upload_to=content.models.upload_split_by_1000),
        ),
        migrations.AlterField(
            model_name='content',
            name='file',
            field=models.FileField(editable=False, storage=django.core.files.storage.FileSystemStorage(location='content'), upload_to=content.models.upload_split_by_1000),
        ),
        migrations.AlterField(
            model_name='content',
            name='preview',
            field=models.ImageField(blank=True, editable=False, storage=django.core.files.storage.FileSystemStorage(location='preview'), upload_to=content.models.upload_split_by_1000),
        ),
        migrations.AlterField(
            model_name='content',
            name='privacy',
            field=models.CharField(choices=[('PRIVATE', 'Private'), ('RESTRICTED', 'Group'), ('PUBLIC', 'Public')], default='PRIVATE', max_length=40, verbose_name='Privacy'),
        ),
        migrations.AlterField(
            model_name='content',
            name='status',
            field=models.CharField(default='UNPROCESSED', editable=False, max_length=40),
        ),
        migrations.AlterField(
            model_name='image',
            name='thumbnail',
            field=models.ImageField(editable=False, storage=django.core.files.storage.FileSystemStorage(location='preview'), upload_to=content.models.upload_split_by_1000),
        ),
        migrations.AlterField(
            model_name='mail',
            name='file',
            field=models.FileField(editable=False, storage=django.core.files.storage.FileSystemStorage(location='/Users/arista/Documents/workspace/var/mail/content'), upload_to=content.models.upload_split_by_1000),
        ),
        migrations.AlterField(
            model_name='mail',
            name='status',
            field=models.CharField(choices=[('UNPROCESSED', 'UNPROCESSED'), ('PROCESSED', 'PROCESSED'), ('DUPLICATE', 'DUPLICATE'), ('FAILED', 'FAILED')], default='UNPROCESSED', max_length=40),
        ),
        migrations.AlterField(
            model_name='video',
            name='thumbnail',
            field=models.ImageField(editable=False, storage=django.core.files.storage.FileSystemStorage(location='preview'), upload_to=content.models.upload_split_by_1000),
        ),
        migrations.AlterField(
            model_name='videoinstance',
            name='file',
            field=models.FileField(editable=False, storage=django.core.files.storage.FileSystemStorage(location='video'), upload_to=content.models.upload_split_by_1000),
        ),
    ]
