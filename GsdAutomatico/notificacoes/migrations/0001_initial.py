from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notificacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('mensagem', 'Mensagem'), ('autorizacao', 'Autorização'), ('sistema', 'Sistema'), ('patd', 'PATD')], default='sistema', max_length=20)),
                ('titulo', models.CharField(max_length=255)),
                ('corpo', models.TextField(blank=True, default='')),
                ('url', models.CharField(blank=True, default='', max_length=500)),
                ('lida', models.BooleanField(db_index=True, default=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('origem_id', models.PositiveIntegerField(blank=True, null=True)),
                ('origem_tipo', models.CharField(blank=True, default='', max_length=100)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_unificadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notificação',
                'verbose_name_plural': 'Notificações',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.AddIndex(
            model_name='notificacao',
            index=models.Index(fields=['usuario', 'lida'], name='notificacoe_usuario_lida_idx'),
        ),
    ]
