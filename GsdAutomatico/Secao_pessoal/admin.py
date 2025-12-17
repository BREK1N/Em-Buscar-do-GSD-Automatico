from django.contrib import admin
from .models import Efetivo

@admin.register(Efetivo)
class EfetivoAdmin(admin.ModelAdmin):
    # Configuração da exibição de Militares no painel de admin.
    list_display = (
        'posto', 'quad', 'especializacao', 'saram', 'nome_completo', 
        'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial'
    )
    search_fields = ('nome_completo', 'nome_guerra', 'saram', 'especializacao')
    list_filter = ('oficial', 'posto', 'quad', 'om', 'setor')
    ordering = ('posto', 'quad', 'nome_guerra')
