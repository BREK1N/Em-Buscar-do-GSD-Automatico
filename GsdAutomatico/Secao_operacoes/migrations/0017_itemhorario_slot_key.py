from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Secao_operacoes', '0016_remove_configuracaooperacoes_chefe_sop_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemhorario',
            name='slot_key',
            field=models.CharField(
                blank=True,
                default='',
                max_length=30,
                verbose_name='Slot padrão vinculado',
            ),
        ),
    ]
