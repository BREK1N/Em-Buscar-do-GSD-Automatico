from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0059_patd_prazo_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='patd',
            name='oficial_aceitou',
            field=models.BooleanField(blank=True, default=None, null=True, verbose_name='Oficial Aceitou Atribuição'),
        ),
    ]
