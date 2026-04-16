# Re-exporta todos os nomes públicos referenciados em urls.py.
# O urls.py não precisa de nenhuma alteração.

from .decorators import (
    comandante_redirect,
    oficial_responsavel_required,
    OuvidoriaAccessMixin,
    ComandanteAccessMixin,
    ouvidoria_required,
    comandante_required,
)

from .helpers import (
    get_next_patd_number,
    format_militar_string,
    buscar_militar_inteligente,
    get_document_pages,
)

from .notifications import (
    patds_expirados_json,
    patd_atribuicoes_pendentes_json,
    extender_prazo_massa,
    verificar_e_atualizar_prazos,
    search_militares_json,
    comandante_pendencias_json,
)

from .signatures import (
    salvar_assinatura,
    salvar_assinatura_ciencia,
    salvar_assinatura_defesa,
    salvar_assinatura_reconsideracao,
    salvar_assinatura_testemunha,
    remover_assinatura,
    lista_oficiais,
    salvar_assinatura_padrao,
    gerenciar_configuracoes_padrao,
)

from .analysis import (
    regenerar_ocorrencia,
    regenerar_resumo_defesa,
    regenerar_texto_relatorio,
    regenerar_punicao,
    analisar_punicao,
    salvar_apuracao,
)

from .commander import (
    ComandanteDashboardView,
    patd_aprovar,
    patd_retornar,
    avancar_para_comandante,
    solicitar_reconsideracao,
    salvar_reconsideracao,
    anexar_documento_reconsideracao_oficial,
)

from .documents import (
    salvar_documento_patd,
    salvar_alegacao_defesa,
    extender_prazo,
    exportar_patd_docx,
    upload_ficha_individual,
    upload_oficio_lancamento,
)

from .militar import (
    MilitarListView,
    MilitarPATDListView,
    MilitarDetailView,
    patd_atribuicoes_pendentes,
    atribuir_oficial,
    aceitar_atribuicao,
)

from .patd import (
    index,
    PATDListView,
    PatdFinalizadoListView,
    PatdArquivadoListView,
    PATDTrashView,
    PATDTrashListView,
    PATDDetailView,
    PATDUpdateView,
    PATDDeleteView,
    patd_restore,
    patd_permanently_delete,
    arquivar_patd,
    desarquivar_patd,
    prosseguir_sem_alegacao,
    excluir_anexo,
    finalizar_publicacao,
    finalizar_patd_completa,
    justificar_patd,
    salvar_nova_punicao,
)
