from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Declara o model Notificacao no app caixa_entrada sem criar tabela,
    pois a tabela já existe em Secao_pessoal_notificacao.
    """

    initial = True

    dependencies = [
        ('Secao_pessoal', '0020_notificacao_anexo'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Notificacao',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('titulo', models.CharField(max_length=200, verbose_name='Assunto')),
                        ('mensagem', models.TextField(verbose_name='Mensagem')),
                        ('lida', models.BooleanField(default=False)),
                        ('arquivada', models.BooleanField(default=False, verbose_name='Arquivada')),
                        ('anexo', models.FileField(blank=True, null=True, upload_to='notificacoes_anexos/', verbose_name='Anexo')),
                        ('deleted', models.BooleanField(default=False, verbose_name='Excluído (Lixeira)')),
                        ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Data de Exclusão')),
                        ('data_criacao', models.DateTimeField(auto_now_add=True)),
                        ('remetente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_enviadas', to='Secao_pessoal.efetivo')),
                        ('destinatario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes_recebidas', to='Secao_pessoal.efetivo')),
                    ],
                    options={
                        'verbose_name': 'Notificação',
                        'verbose_name_plural': 'Notificações',
                        'db_table': 'Secao_pessoal_notificacao',
                        'ordering': ['-data_criacao'],
                    },
                ),
            ],
            database_operations=[],  # Tabela já existe — não criar nem alterar
        ),
    ]
