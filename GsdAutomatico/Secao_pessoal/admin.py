from django.contrib import admin
from .models import Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor

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

# Registrando as novas models para aparecerem no admin
@admin.register(Posto)
class PostoAdmin(admin.ModelAdmin):
    search_fields = ['nome']

@admin.register(Quad)
class QuadAdmin(admin.ModelAdmin):
    search_fields = ['nome']

@admin.register(Especializacao)
class EspecializacaoAdmin(admin.ModelAdmin):
    search_fields = ['nome']

@admin.register(OM)
class OMAdmin(admin.ModelAdmin):
    search_fields = ['nome']

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    search_fields = ['nome']

@admin.register(Subsetor)
class SubsetorAdmin(admin.ModelAdmin):
    search_fields = ['nome']
