from django.contrib import admin
from .models import Militar, PATD

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

@admin.register(PATD)
class PATDAdmin(admin.ModelAdmin):
    
    # Configuração da exibição de PATDs no painel de admin.
    list_display = ('numero_patd', 'militar', 'transgressao_resumida', 'oficial_responsavel', 'data_inicio', 'data_termino')
    search_fields = ('numero_patd', 'militar__nome_completo', 'militar__nome_guerra')
    list_filter = ('data_inicio', 'data_termino', 'oficial_responsavel')
    autocomplete_fields = ['militar', 'oficial_responsavel'] # Facilita a busca de militares
    ordering = ('-data_inicio',)

    def transgressao_resumida(self, obj):
        """
        Mostra apenas os primeiros 75 caracteres da transgressão na lista.
        """
        if len(obj.transgressao) > 75:
            return obj.transgressao[:75] + '...'
        return obj.transgressao
    transgressao_resumida.short_description = 'Transgressão'