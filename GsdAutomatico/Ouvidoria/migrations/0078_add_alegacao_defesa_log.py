import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0077_configuracao_oficial_chefe_ouvidoria_patd_oficial_assinou_analise'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AlegacaoDefesaLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto_original', models.TextField(verbose_name='Texto Original')),
                ('texto_novo', models.TextField(verbose_name='Texto Novo')),
                ('data_alteracao', models.DateTimeField(auto_now_add=True, verbose_name='Data da Alteração')),
                ('patd', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='logs_alegacao_defesa',
                    to='Ouvidoria.patd',
                    verbose_name='PATD',
                )),
                ('usuario', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuário',
                )),
            ],
            options={
                'verbose_name': 'Log de Alteração da Alegação de Defesa',
                'verbose_name_plural': 'Logs de Alteração da Alegação de Defesa',
                'ordering': ['-data_alteracao'],
            },
        ),
    ]
