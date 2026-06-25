# ==========================================
# AUDITORIA (Fase 3)
# ==========================================
from auditoria.registry import registrar_modelo
from auditoria.utils import resolver_label
from .models import Efetivo

_PESSOAL_PERMISSAO_MAP = {
    'Seção de Pessoal (S1)': 'S1- Efetivo',
}

registrar_modelo(
    Efetivo, secao='pessoal', objeto_tipo='Efetivo', label='o militar',
    permissao_resolver=lambda user: resolver_label(user, _PESSOAL_PERMISSAO_MAP),
    campo_id=lambda e: e.nome_guerra or e.nome_completo,
    campos_monitorados=['posto', 'situacao', 'setor', 'subsetor', 'om'],
)
