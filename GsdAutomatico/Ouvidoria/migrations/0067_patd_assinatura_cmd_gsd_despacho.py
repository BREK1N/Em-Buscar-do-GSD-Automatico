from django.db import migrations, models
import Ouvidoria.models


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0066_add_assinatura_cmd_gsd_despacho_abertura'),
    ]

    operations = [
        migrations.AddField(
            model_name='patd',
            name='assinatura_cmd_gsd_despacho',
            field=models.FileField(
                blank=True,
                max_length=255,
                null=True,
                upload_to=Ouvidoria.models.patd_signature_path,
                verbose_name='Assinatura CMD GSD – Despacho de Abertura',
            ),
        ),
    ]
