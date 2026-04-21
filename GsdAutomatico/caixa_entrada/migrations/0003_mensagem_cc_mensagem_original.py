from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('caixa_entrada', '0002_mensagem_leitura_anexo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='mensagem',
            name='cc',
            field=models.ManyToManyField(
                blank=True,
                related_name='mensagens_cc',
                to=settings.AUTH_USER_MODEL,
                verbose_name='CC (com cópia)',
            ),
        ),
        migrations.AddField(
            model_name='mensagem',
            name='mensagem_original',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='respostas',
                to='caixa_entrada.mensagem',
                verbose_name='Resposta a',
            ),
        ),
    ]
