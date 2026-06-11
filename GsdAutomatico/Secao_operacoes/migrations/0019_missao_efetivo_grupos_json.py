from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Secao_operacoes', '0018_unique_omis_numero_por_ano'),
    ]

    operations = [
        migrations.AddField(
            model_name='missao',
            name='efetivo_grupos_json',
            field=models.TextField(blank=True, default='', verbose_name='Grupos de Efetivo (JSON)'),
        ),
    ]
