# Generated by Django 3.2.5 on 2021-07-15 06:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tournaments", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tournamentmember",
            name="team",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="tournaments.tournamentteam",
            ),
        ),
    ]
