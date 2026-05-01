from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0003_userprofile_force_password_change'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='foto',
            field=models.ImageField(blank=True, null=True, upload_to='perfis/', verbose_name='Foto de Perfil'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='ramal',
            field=models.CharField(blank=True, max_length=20, verbose_name='Ramal'),
        ),
    ]
