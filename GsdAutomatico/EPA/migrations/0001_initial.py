from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('Secao_pessoal', '0024_alter_efetivo_deleted'),
        ('Secao_operacoes', '0021_situacaoespecialefetivo'),
    ]

    operations = [
        migrations.CreateModel(
            name='EscalaMissaoEPA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identificacao_pelotao', models.CharField(blank=True, default='', max_length=100, verbose_name='Identificação do Pelotão/Seção')),
                ('grupos_json', models.TextField(blank=True, default='', verbose_name='Grupos por Função (JSON)')),
                ('observacoes', models.TextField(blank=True, verbose_name='Observações')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('militares', models.ManyToManyField(blank=True, related_name='escalas_epa', to='Secao_pessoal.efetivo', verbose_name='Militares Escalados')),
                ('missao', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='escala_epa', to='Secao_operacoes.missao', verbose_name='Missão')),
            ],
            options={
                'verbose_name': 'Escala EPA',
                'verbose_name_plural': 'Escalas EPA',
                'ordering': ['-missao__data_missao'],
            },
        ),
    ]
