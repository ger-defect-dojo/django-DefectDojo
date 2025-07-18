# Generated by Django 5.1.8 on 2025-05-14 06:35

import dojo.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dojo', '0230_add_finding_kev_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='finding',
            name='cvssv3',
            field=models.TextField(help_text='Common Vulnerability Scoring System version 3 (CVSSv3) score associated with this finding.', max_length=117, null=True, validators=[dojo.validators.cvss3_validator], verbose_name='CVSS v3 vector'),
        ),
        migrations.AlterField(
            model_name='finding_template',
            name='cvssv3',
            field=models.TextField(help_text='Common Vulnerability Scoring System version 3 (CVSSv3) score associated with this finding.', max_length=117, null=True, validators=[dojo.validators.cvss3_validator], verbose_name='CVSS v3 vector'),
        ),
    ]
