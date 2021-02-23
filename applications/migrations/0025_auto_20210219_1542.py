# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2021-02-19 07:42
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0024_compliance_external_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='old_application',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='application_old_application', to='applications.Application'),
        ),
        migrations.AlterField(
            model_name='application',
            name='state',
            field=models.IntegerField(choices=[(0, 'Unknown'), (1, 'Draft'), (2, 'With Admin Officer'), (3, 'With Referrals'), (4, 'With Assessor'), (5, 'With Manager'), (6, 'Issued'), (7, 'Issued (with admin)'), (8, 'Declined'), (9, 'New'), (10, 'Approved'), (11, 'Expired'), (12, 'With Director'), (13, 'With Executive'), (14, 'Completed'), (15, 'Form Creator'), (16, 'Current'), (17, 'Deleted'), (18, 'Pending Payment'), (19, 'Not Supported')], default=1),
        ),
    ]
