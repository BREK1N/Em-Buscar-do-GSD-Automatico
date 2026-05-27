from django.db import migrations


def limpar_oficial_pos_defesa(apps, schema_editor):
    """
    PATDs em 'definicao_oficial' que já têm oficial_responsavel setado chegaram
    aqui via alegação de defesa (ciclo 2). O campo precisa ser limpo para que a
    condição de reatribuição no PATD.save() funcione corretamente.
    Em migration context, PATD.objects usa o Manager base do Django (sem filtro
    de deleted), então inclui todos os registros.
    """
    PATD = apps.get_model('Ouvidoria', 'PATD')
    Anexo = apps.get_model('Ouvidoria', 'Anexo')

    ids_com_defesa_texto = set(
        PATD.objects.filter(
            status='definicao_oficial',
            oficial_responsavel__isnull=False,
            alegacao_defesa__isnull=False,
        ).exclude(alegacao_defesa='').values_list('id', flat=True)
    )

    ids_com_defesa_anexo = set(
        Anexo.objects.filter(
            tipo='defesa',
            patd__status='definicao_oficial',
            patd__oficial_responsavel__isnull=False,
        ).values_list('patd_id', flat=True)
    )

    ids_afetados = ids_com_defesa_texto | ids_com_defesa_anexo

    if ids_afetados:
        atualizadas = PATD.objects.filter(pk__in=ids_afetados).update(
            oficial_responsavel=None,
            oficial_aceitou=None,
        )
        print(f"\n  [0071] {atualizadas} PATD(s) corrigida(s): oficial_responsavel e oficial_aceitou limpos.")
    else:
        print("\n  [0071] Nenhuma PATD afetada encontrada.")


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0070_alter_patd_status'),
    ]

    operations = [
        migrations.RunPython(limpar_oficial_pos_defesa, migrations.RunPython.noop),
    ]
