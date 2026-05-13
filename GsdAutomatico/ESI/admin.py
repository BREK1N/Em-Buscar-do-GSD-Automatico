from django.contrib import admin
from .models import EscalaMissaoESI

@admin.register(EscalaMissaoESI)
class EscalaMissaoESIAdmin(admin.ModelAdmin):
    list_display = ['missao', 'criado_em']
    filter_horizontal = ['militares']
