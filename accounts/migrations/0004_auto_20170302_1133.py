# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-02 03:33
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_auto_20170223_1330'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailuserprofile',
            name='dob',
            field=models.DateField(blank=True, null=True, verbose_name='date of birth'),
        ),
        migrations.AlterField(
            model_name='emailuserprofile',
            name='emailuser',
            field=models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='emailuserprofile',
            name='id_verified',
            field=models.DateField(blank=True, null=True, verbose_name='ID verified'),
        ),
    ]
