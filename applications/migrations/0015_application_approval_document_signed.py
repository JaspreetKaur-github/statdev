# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2020-01-16 09:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0014_application_approval_document'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='approval_document_signed',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='application_approval_document_signed', to='applications.Record'),
        ),
    ]
