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
            name='Chamado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('protocolo', models.CharField(editable=False, max_length=9, unique=True)),
                ('titulo', models.CharField(max_length=300)),
                ('descricao', models.TextField()),
                ('status', models.CharField(
                    choices=[
                        ('aberto', 'Aberto'),
                        ('em_atendimento', 'Em Atendimento'),
                        ('aguardando_solicitante', 'Aguardando Solicitante'),
                        ('resolvido', 'Resolvido'),
                        ('fechado', 'Fechado'),
                    ],
                    default='aberto', max_length=30,
                )),
                ('prioridade', models.CharField(
                    choices=[
                        ('baixa', 'Baixa'),
                        ('normal', 'Normal'),
                        ('alta', 'Alta'),
                        ('critica', 'Crítica'),
                    ],
                    default='normal', max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fechado_em', models.DateTimeField(blank=True, null=True)),
                ('solicitante', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='chamados_abertos',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('atribuido_a', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='chamados_atribuidos',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Chamado',
                'verbose_name_plural': 'Chamados',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MensagemChamado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField()),
                ('eh_sistema', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chamado', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mensagens',
                    to='chamados.chamado',
                )),
                ('autor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='AnexoChamado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arquivo', models.FileField(upload_to='chamados/anexos/%Y/%m/')),
                ('nome', models.CharField(max_length=255)),
                ('tamanho', models.PositiveIntegerField()),
                ('mensagem', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='anexos',
                    to='chamados.mensagemchamado',
                )),
            ],
        ),
    ]
