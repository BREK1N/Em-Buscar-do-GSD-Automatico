from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('caixa_entrada', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Mensagem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assunto', models.CharField(max_length=255, verbose_name='Assunto')),
                ('corpo', models.TextField(verbose_name='Mensagem')),
                ('tipo', models.CharField(choices=[('mensagem', 'Mensagem'), ('chamado', 'Chamado')], default='mensagem', max_length=10, verbose_name='Tipo')),
                ('status_chamado', models.CharField(blank=True, choices=[('aberto', 'Aberto'), ('em_andamento', 'Em Andamento'), ('resolvido', 'Resolvido')], max_length=15, null=True, verbose_name='Status do Chamado')),
                ('data_envio', models.DateTimeField(auto_now_add=True, verbose_name='Data de Envio')),
                ('eh_rascunho', models.BooleanField(default=False, verbose_name='Rascunho')),
                ('remetente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensagens_enviadas', to=settings.AUTH_USER_MODEL, verbose_name='Remetente')),
                ('destinatarios', models.ManyToManyField(related_name='mensagens_recebidas', to=settings.AUTH_USER_MODEL, verbose_name='Destinatários')),
                ('excluida_por', models.ManyToManyField(blank=True, related_name='mensagens_excluidas', to=settings.AUTH_USER_MODEL, verbose_name='Excluída por')),
            ],
            options={
                'verbose_name': 'Mensagem',
                'verbose_name_plural': 'Mensagens',
                'ordering': ['-data_envio'],
                'permissions': [('gerenciar_chamados', 'Pode gerenciar chamados')],
            },
        ),
        migrations.CreateModel(
            name='LeituraMensagem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_leitura', models.DateTimeField(auto_now_add=True)),
                ('mensagem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='caixa_entrada.mensagem')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Leitura',
                'verbose_name_plural': 'Leituras',
                'unique_together': {('mensagem', 'usuario')},
            },
        ),
        migrations.AddField(
            model_name='mensagem',
            name='lida_por',
            field=models.ManyToManyField(blank=True, related_name='mensagens_lidas', through='caixa_entrada.LeituraMensagem', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='Anexo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arquivo', models.FileField(upload_to='inbox/anexos/%Y/%m/', verbose_name='Arquivo')),
                ('nome_original', models.CharField(max_length=255, verbose_name='Nome original')),
                ('tamanho', models.IntegerField(verbose_name='Tamanho (bytes)')),
                ('tipo_mime', models.CharField(max_length=100, verbose_name='Tipo MIME')),
                ('mensagem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='anexos', to='caixa_entrada.mensagem', verbose_name='Mensagem')),
            ],
            options={
                'verbose_name': 'Anexo',
                'verbose_name_plural': 'Anexos',
            },
        ),
    ]
