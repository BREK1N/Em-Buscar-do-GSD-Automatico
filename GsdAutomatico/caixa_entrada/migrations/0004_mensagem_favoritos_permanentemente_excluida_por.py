from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caixa_entrada', '0003_mensagem_cc_mensagem_original'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='mensagem',
            name='permanentemente_excluida_por',
            field=models.ManyToManyField(
                blank=True,
                related_name='mensagens_perm_excluidas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Excluída permanentemente por',
            ),
        ),
        migrations.AddField(
            model_name='mensagem',
            name='favoritos',
            field=models.ManyToManyField(
                blank=True,
                related_name='mensagens_favoritas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Favoritos',
            ),
        ),
    ]
