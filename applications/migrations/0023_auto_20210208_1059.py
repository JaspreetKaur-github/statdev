# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2021-02-08 02:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0022_compliance_external_comments'),
    ]

    operations = [
        migrations.AlterField(
            model_name='referral',
            name='sent_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
