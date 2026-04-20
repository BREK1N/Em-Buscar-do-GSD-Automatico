from django.db import migrations


def auto_accept_existing_oficiais(apps, schema_editor):
    """PATDs que já tinham oficial atribuído antes desta feature são consideradas aceitas."""
    PATD = apps.get_model('Ouvidoria', 'PATD')
    PATD.objects.filter(
        oficial_responsavel__isnull=False,
        oficial_aceitou__isnull=True,
    ).update(oficial_aceitou=True)


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0060_patd_oficial_aceitou'),
    ]

    operations = [
        migrations.RunPython(auto_accept_existing_oficiais, migrations.RunPython.noop),
    ]
