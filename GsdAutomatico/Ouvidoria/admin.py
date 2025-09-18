from django.contrib import admin
from .models import Militar, PATD, Anexo

@admin.register(Militar)
class MilitarAdmin(admin.ModelAdmin):
    # Configuração da exibição de Militares no painel de admin.
    list_display = (
        'posto', 'quad', 'especializacao', 'saram', 'nome_completo', 
        'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial'
    )
    search_fields = ('nome_completo', 'nome_guerra', 'saram', 'especializacao')
    list_filter = ('oficial', 'posto', 'quad', 'om', 'setor')
    ordering = ('posto', 'quad', 'nome_guerra')

class AnexoInline(admin.TabularInline):
    model = Anexo
    extra = 1
    readonly_fields = ('data_upload',)

@admin.register(PATD)
class PATDAdmin(admin.ModelAdmin):
    
    # Configuração da exibição de PATDs no painel de admin.
    list_display = ('numero_patd', 'militar', 'status', 'transgressao_resumida', 'oficial_responsavel', 'data_ocorrencia', 'data_inicio')
    search_fields = ('numero_patd', 'militar__nome_completo', 'militar__nome_guerra')
    list_filter = ('status', 'data_ocorrencia', 'data_inicio', 'oficial_responsavel')
    autocomplete_fields = ['militar', 'oficial_responsavel'] 
    ordering = ('-data_inicio',)
    # TORNA O CAMPO STATUS APENAS LEITURA NO ADMIN
    readonly_fields = ('status',)
    inlines = [AnexoInline]


    def transgressao_resumida(self, obj):
        """
        Mostra apenas os primeiros 75 caracteres da transgressão na lista.
        """
        if len(obj.transgressao) > 75:
            return obj.transgressao[:75] + '...'
        return obj.transgressao
    transgressao_resumida.short_description = 'Transgressão'
