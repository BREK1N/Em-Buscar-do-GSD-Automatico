# Generated manually on 2026-06-30
# Corrige perda de dados: PATD.militar usava on_delete=CASCADE, apagando
# PATDs inteiras quando o militar era excluído. Passa para SET_NULL e
# adiciona campos de retrato (snapshot) para manter a PATD identificável
# mesmo depois que o militar for excluído do sistema.

import django.db.models.deletion
from django.db import migrations, models


def backfill_militar_snapshot(apps, schema_editor):
    # F() com join não é suportado em .update() — usa SQL raw com UPDATE...FROM
    schema_editor.execute("""
        UPDATE "Ouvidoria_patd" p
        SET
            militar_nome_completo_snapshot = e.nome_completo,
            militar_nome_guerra_snapshot   = e.nome_guerra,
            militar_posto_snapshot         = e.posto,
            militar_saram_snapshot         = e.saram
        FROM "Efetivo" e
        WHERE p.militar_id = e.id
          AND p.militar_id IS NOT NULL
    """)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0080_patd_numero_patd_legado_patd_sistema_antigo'),
        ('Secao_pessoal', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patd',
            name='militar',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='patds',
                to='Secao_pessoal.efetivo',
                verbose_name='Militar Acusado',
            ),
        ),
        migrations.AddField(
            model_name='patd',
            name='militar_nome_completo_snapshot',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Nome Completo do Militar (registro histórico)'),
        ),
        migrations.AddField(
            model_name='patd',
            name='militar_nome_guerra_snapshot',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Nome de Guerra do Militar (registro histórico)'),
        ),
        migrations.AddField(
            model_name='patd',
            name='militar_posto_snapshot',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Posto/Graduação do Militar (registro histórico)'),
        ),
        migrations.AddField(
            model_name='patd',
            name='militar_saram_snapshot',
            field=models.IntegerField(blank=True, null=True, verbose_name='SARAM do Militar (registro histórico)'),
        ),
        migrations.RunPython(backfill_militar_snapshot, noop),
    ]
