import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CarouselSlide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200, verbose_name='Título')),
                ('subtitle', models.TextField(blank=True, verbose_name='Subtítulo')),
                ('image', models.ImageField(upload_to='home/carousel/', verbose_name='Imagem')),
                ('link_url', models.CharField(blank=True, max_length=500, verbose_name='Link (URL)')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('active', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='carousel_slides', to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
            ],
            options={
                'verbose_name': 'Slide do Carrossel',
                'verbose_name_plural': 'Slides do Carrossel',
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='Tutorial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300, verbose_name='Título')),
                ('content', models.TextField(verbose_name='Conteúdo')),
                ('cover_image', models.ImageField(blank=True, null=True, upload_to='home/tutorials/covers/', verbose_name='Imagem de Capa')),
                ('category', models.CharField(blank=True, max_length=100, verbose_name='Categoria')),
                ('published', models.BooleanField(default=True, verbose_name='Publicado')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tutorials', to=settings.AUTH_USER_MODEL, verbose_name='Autor')),
            ],
            options={
                'verbose_name': 'Tutorial',
                'verbose_name_plural': 'Tutoriais',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TutorialAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='home/tutorials/attachments/', verbose_name='Arquivo')),
                ('name', models.CharField(max_length=200, verbose_name='Nome do Arquivo')),
                ('description', models.CharField(blank=True, max_length=300, verbose_name='Descrição')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('tutorial', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='home.tutorial', verbose_name='Tutorial')),
            ],
            options={
                'verbose_name': 'Anexo do Tutorial',
                'verbose_name_plural': 'Anexos do Tutorial',
            },
        ),
        migrations.CreateModel(
            name='TutorialImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='home/tutorials/images/', verbose_name='Imagem')),
                ('caption', models.CharField(blank=True, max_length=300, verbose_name='Legenda')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('tutorial', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='home.tutorial', verbose_name='Tutorial')),
            ],
            options={
                'verbose_name': 'Imagem do Tutorial',
                'verbose_name_plural': 'Imagens do Tutorial',
                'ordering': ['order'],
            },
        ),
    ]
