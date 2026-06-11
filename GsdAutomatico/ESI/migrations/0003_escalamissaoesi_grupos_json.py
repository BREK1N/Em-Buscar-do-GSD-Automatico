from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ESI', '0002_escalamissaoesi_identificacao_pelotao'),
    ]

    operations = [
        migrations.AddField(
            model_name='escalamissaoesi',
            name='grupos_json',
            field=models.TextField(blank=True, default='', verbose_name='Grupos por Função (JSON)'),
        ),
    ]
