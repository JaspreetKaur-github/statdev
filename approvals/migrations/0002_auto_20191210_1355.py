# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2019-12-10 05:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approvals', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='approval',
            name='app_type',
            field=models.IntegerField(choices=[(1, 'Permit'), (2, 'Licence/permit'), (3, 'Part 5'), (4, 'Emergency works'), (5, 'Part 5 - Amendment Request'), (6, 'Section 84'), (7, 'Test - Application'), (8, 'Amend Permit'), (9, 'Amend Licence'), (10, 'Renew Permit'), (11, 'Renew Licence')]),
        ),
    ]
