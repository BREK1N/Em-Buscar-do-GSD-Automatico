from django.contrib import admin
from django.utils import timezone
from .models import Mensagem, LeituraMensagem, Anexo, Notificacao


class AnexoInline(admin.TabularInline):
    model = Anexo
    extra = 0
    readonly_fields = ('nome_original', 'tamanho', 'tipo_mime')


class LeituraInline(admin.TabularInline):
    model = LeituraMensagem
    extra = 0
    readonly_fields = ('usuario', 'data_leitura')
    can_delete = False


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ('assunto', 'remetente', 'tipo', 'status_chamado', 'data_envio', 'eh_rascunho')
    list_filter = ('tipo', 'status_chamado', 'eh_rascunho', 'data_envio')
    search_fields = ('assunto', 'remetente__username', 'remetente__first_name')
    readonly_fields = ('data_envio',)
    inlines = [AnexoInline, LeituraInline]
    filter_horizontal = ('destinatarios',)
    actions = ['marcar_chamados_resolvidos']

    def marcar_chamados_resolvidos(self, request, queryset):
        updated = queryset.filter(tipo='chamado').update(status_chamado='resolvido')
        self.message_user(request, f"{updated} chamado(s) marcado(s) como resolvido.")
    marcar_chamados_resolvidos.short_description = "Marcar chamados selecionados como resolvidos"


@admin.register(Anexo)
class AnexoAdmin(admin.ModelAdmin):
    list_display = ('nome_original', 'mensagem', 'tipo_mime', 'tamanho')
    search_fields = ('nome_original', 'mensagem__assunto')


@admin.register(LeituraMensagem)
class LeituraMensagemAdmin(admin.ModelAdmin):
    list_display = ('mensagem', 'usuario', 'data_leitura')
    list_filter = ('data_leitura',)
    readonly_fields = ('data_leitura',)


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'remetente', 'destinatario', 'lida', 'data_criacao')
    list_filter = ('lida', 'arquivada', 'deleted')
    search_fields = ('titulo', 'remetente__nome_guerra', 'destinatario__nome_guerra')
