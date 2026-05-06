from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Secao_operacoes', '0011_missao_horarios_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracaooperacoes',
            name='observacoes_armamento_padrao',
            field=models.CharField(blank=True, default='', max_length=300, verbose_name='Armamento conforme RIMB (padrão)'),
        ),
    ]
