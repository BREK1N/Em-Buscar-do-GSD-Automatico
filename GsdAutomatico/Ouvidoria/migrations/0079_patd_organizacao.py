from datetime import date
import django.db.models.functions
from django.db import migrations, models


def popular_organizacao(apps, schema_editor):
    BINFAE_START = date(2026, 6, 1)
    PATD = apps.get_model('Ouvidoria', 'PATD')
    PATD.objects.filter(data_inicio__date__lt=BINFAE_START).update(organizacao='GSD')
    PATD.objects.filter(data_inicio__date__gte=BINFAE_START).update(organizacao='BINFAE')


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0078_add_alegacao_defesa_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='patd',
            name='organizacao',
            field=models.CharField(
                choices=[('GSD', 'GSD'), ('BINFAE', 'BINFAE')],
                db_index=True,
                default='BINFAE',
                max_length=10,
                verbose_name='Organização',
            ),
        ),
        migrations.RunPython(popular_organizacao, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='patd',
            name='unique_patd_numero_por_ano',
        ),
        migrations.AddConstraint(
            model_name='patd',
            constraint=models.UniqueConstraint(
                django.db.models.functions.ExtractYear('data_inicio'),
                'numero_patd',
                'organizacao',
                condition=models.Q(numero_patd__isnull=False),
                name='unique_patd_numero_por_ano_org',
            ),
        ),
    ]
