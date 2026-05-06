from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Secao_operacoes', '0010_configuracaooperacoes_diretriz_padrao_1_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='missao',
            name='horarios_config',
            field=models.TextField(blank=True, default='', verbose_name='Configuração de horários (JSON)'),
        ),
    ]
