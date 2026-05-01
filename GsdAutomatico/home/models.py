from django.db import models
from django.contrib.auth.models import User


class CarouselSlide(models.Model):
    title = models.CharField(max_length=200, blank=True, verbose_name='Título')
    subtitle = models.TextField(blank=True, verbose_name='Subtítulo')
    image = models.ImageField(upload_to='home/carousel/', verbose_name='Imagem')
    link_url = models.CharField(max_length=500, blank=True, verbose_name='Link (URL)')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    active = models.BooleanField(default=True, verbose_name='Ativo')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='carousel_slides', verbose_name='Criado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Slide do Carrossel'
        verbose_name_plural = 'Slides do Carrossel'

    def __str__(self):
        return self.title or f'Slide #{self.pk}'


class Tutorial(models.Model):
    title = models.CharField(max_length=300, verbose_name='Título')
    content = models.TextField(verbose_name='Conteúdo')
    cover_image = models.ImageField(
        upload_to='home/tutorials/covers/', blank=True, null=True,
        verbose_name='Imagem de Capa'
    )
    category = models.CharField(max_length=100, blank=True, verbose_name='Categoria')
    author = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='tutorials', verbose_name='Autor'
    )
    published = models.BooleanField(default=True, verbose_name='Publicado')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tutorial'
        verbose_name_plural = 'Tutoriais'

    def __str__(self):
        return self.title


class TutorialImage(models.Model):
    tutorial = models.ForeignKey(
        Tutorial, on_delete=models.CASCADE,
        related_name='images', verbose_name='Tutorial'
    )
    image = models.ImageField(upload_to='home/tutorials/images/', verbose_name='Imagem')
    caption = models.CharField(max_length=300, blank=True, verbose_name='Legenda')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordem')

    class Meta:
        ordering = ['order']
        verbose_name = 'Imagem do Tutorial'
        verbose_name_plural = 'Imagens do Tutorial'

    def __str__(self):
        return f'Imagem #{self.order} — {self.tutorial.title}'


class TutorialAttachment(models.Model):
    tutorial = models.ForeignKey(
        Tutorial, on_delete=models.CASCADE,
        related_name='attachments', verbose_name='Tutorial'
    )
    file = models.FileField(upload_to='home/tutorials/attachments/', verbose_name='Arquivo')
    name = models.CharField(max_length=200, verbose_name='Nome do Arquivo')
    description = models.CharField(max_length=300, blank=True, verbose_name='Descrição')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Anexo do Tutorial'
        verbose_name_plural = 'Anexos do Tutorial'

    def __str__(self):
        return self.name
