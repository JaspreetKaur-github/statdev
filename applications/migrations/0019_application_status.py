# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2021-01-23 08:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0018_auto_20201208_1152'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='status',
            field=models.IntegerField(choices=[(1, 'Active'), (2, 'Cancelled')], default=1),
        ),
    ]
