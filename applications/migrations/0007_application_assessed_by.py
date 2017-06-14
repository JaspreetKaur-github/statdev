# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-06-09 02:32
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('applications', '0006_auto_20170608_1549'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='assessed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='assessed_by', to=settings.AUTH_USER_MODEL),
        ),
    ]