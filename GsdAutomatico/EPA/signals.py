# ==========================================
# AUDITORIA (Fase 3)
# ==========================================
from auditoria.registry import registrar_modelo
from auditoria.utils import resolver_label
from .models import EscalaMissaoEPA

_EPA_PERMISSAO_MAP = {
    'EPA - Missões': 'EPA- Missões',
}

registrar_modelo(
    EscalaMissaoEPA, secao='epa', objeto_tipo='Escala EPA', label='a escala EPA da missão',
    permissao_resolver=lambda user: resolver_label(user, _EPA_PERMISSAO_MAP),
    campo_id=lambda e: e.missao.numero,
    campos_monitorados=['identificacao_pelotao', 'observacoes'],
)
