import logging
import openai
from celery import shared_task

logger = logging.getLogger(__name__)

# Delays de retry: 10s para erros genéricos, 60s para RateLimitError
_RATE_LIMIT_DELAY = 60
_DEFAULT_DELAY = 10


def _retry_task(self, exc, patd_pk, task_name):
    """Escolhe o delay correto e relança o retry. Não retenta cota esgotada."""
    if isinstance(exc, openai.RateLimitError) and 'insufficient_quota' in str(exc):
        logger.error(
            "%s abortado (pk=%s): cota OpenAI esgotada — recarregue créditos em platform.openai.com",
            task_name, patd_pk,
        )
        raise exc  # não retenta — créditos não voltam sozinhos
    delay = _RATE_LIMIT_DELAY if isinstance(exc, openai.RateLimitError) else _DEFAULT_DELAY
    logger.warning(
        "%s falhou (pk=%s): %s — retry em %ds",
        task_name, patd_pk, exc, delay,
    )
    raise self.retry(exc=exc, countdown=delay)


@shared_task(bind=True, max_retries=3, time_limit=120)
def regenerar_ocorrencia_task(self, patd_pk):
    from .models import PATD
    from .analise_transgressao import reescrever_ocorrencia
    patd = PATD.objects.get(pk=patd_pk)
    try:
        nova_ocorrencia = reescrever_ocorrencia(patd.transgressao)
        patd.ocorrencia_reescrita = nova_ocorrencia
        patd.comprovante = nova_ocorrencia
        patd.save(update_fields=['ocorrencia_reescrita', 'comprovante'])
        return {'novo_texto': nova_ocorrencia}
    except Exception as exc:
        logger.error("regenerar_ocorrencia_task falhou (pk=%s): %s", patd_pk, exc, exc_info=True)
        _retry_task(self, exc, patd_pk, "regenerar_ocorrencia_task")


@shared_task(bind=True, max_retries=3, time_limit=120)
def regenerar_resumo_defesa_task(self, patd_pk):
    from .models import PATD
    from .analise_transgressao import analisar_e_resumir_defesa
    patd = PATD.objects.get(pk=patd_pk)
    if not patd.alegacao_defesa:
        raise ValueError('Não há texto de defesa para resumir.')
    try:
        novo_resumo = analisar_e_resumir_defesa(patd.alegacao_defesa)
        patd.alegacao_defesa_resumo = novo_resumo
        patd.save(update_fields=['alegacao_defesa_resumo'])
        return {'novo_texto': novo_resumo}
    except Exception as exc:
        logger.error("regenerar_resumo_defesa_task falhou (pk=%s): %s", patd_pk, exc, exc_info=True)
        _retry_task(self, exc, patd_pk, "regenerar_resumo_defesa_task")


@shared_task(bind=True, max_retries=3, time_limit=120)
def regenerar_texto_relatorio_task(self, patd_pk):
    from .models import PATD
    from .analise_transgressao import texto_relatorio
    patd = PATD.objects.get(pk=patd_pk)
    try:
        novo_relatorio = texto_relatorio(patd.transgressao, patd.alegacao_defesa)
        patd.texto_relatorio = novo_relatorio
        patd.save(update_fields=['texto_relatorio'])
        return {'novo_texto': novo_relatorio}
    except Exception as exc:
        logger.error("regenerar_texto_relatorio_task falhou (pk=%s): %s", patd_pk, exc, exc_info=True)
        _retry_task(self, exc, patd_pk, "regenerar_texto_relatorio_task")


@shared_task(bind=True, max_retries=3, time_limit=120)
def regenerar_punicao_task(self, patd_pk):
    from .models import PATD
    from .analise_transgressao import sugere_punicao
    patd = PATD.objects.get(pk=patd_pk)
    try:
        punicao_obj = sugere_punicao(
            transgressao=patd.transgressao,
            agravantes=patd.circunstancias.get('agravantes', []),
            atenuantes=patd.circunstancias.get('atenuantes', []),
            itens=patd.itens_enquadrados,
            observacao="Regeneração de punição",
        )
        nova_punicao_sugerida = punicao_obj.punicao.get('punicao', 'Erro na sugestão.')
        patd.punicao_sugerida = nova_punicao_sugerida
        patd.save(update_fields=['punicao_sugerida'])
        return {'novo_texto': nova_punicao_sugerida}
    except Exception as exc:
        logger.error("regenerar_punicao_task falhou (pk=%s): %s", patd_pk, exc, exc_info=True)
        _retry_task(self, exc, patd_pk, "regenerar_punicao_task")


@shared_task(bind=True, max_retries=3, time_limit=300)
def analisar_punicao_task(self, patd_pk, force_reanalyze=False):
    """Análise completa de IA: enquadramento + agravantes/atenuantes + punição."""
    from .models import PATD
    from .analise_transgressao import enquadra_item, verifica_agravante_atenuante, sugere_punicao

    patd = PATD.objects.select_related('militar').get(pk=patd_pk)
    try:
        itens_obj = enquadra_item(patd.transgressao)
        patd.itens_enquadrados = [item for item in itens_obj.item]

        militar_acusado = patd.militar
        patds_anteriores = PATD.objects.filter(
            militar=militar_acusado
        ).exclude(pk=patd.pk).order_by('-data_inicio')

        has_mau = PATD.objects.filter(
            militar=militar_acusado,
            comportamento="Mau comportamento",
        ).exclude(pk=patd.pk).exists()
        comportamento_anterior = "Mau comportamento" if has_mau else 'Permanece no "Bom comportamento"'

        historico_list = []
        for p_antiga in patds_anteriores:
            if p_antiga.itens_enquadrados and isinstance(p_antiga.itens_enquadrados, list):
                itens_str = ", ".join(
                    f"Item {item.get('numero')}"
                    for item in p_antiga.itens_enquadrados
                    if 'numero' in item
                )
                if itens_str:
                    historico_list.append(
                        f"PATD anterior (Nº {p_antiga.numero_patd}) foi enquadrada em: {itens_str}."
                    )

        historico_militar = "\n".join(historico_list) if historico_list else "Nenhuma punição anterior registrada."
        justificativa = patd.alegacao_defesa or "Nenhuma alegação de defesa foi apresentada."

        circunstancias_obj = verifica_agravante_atenuante(
            historico_militar,
            patd.transgressao,
            justificativa,
            patd.itens_enquadrados,
            comportamento_anterior,
        )
        circunstancias_dict = circunstancias_obj.item[0]
        patd.circunstancias = {
            'atenuantes': circunstancias_dict.get('atenuantes', []),
            'agravantes': circunstancias_dict.get('agravantes', []),
        }

        punicao_obj = sugere_punicao(
            transgressao=patd.transgressao,
            agravantes=patd.circunstancias.get('agravantes', []),
            atenuantes=patd.circunstancias.get('atenuantes', []),
            itens=patd.itens_enquadrados,
            observacao="Análise inicial",
        )
        patd.punicao_sugerida = punicao_obj.punicao.get('punicao', 'Erro na sugestão.')
        patd.save()

        return {
            'itens': patd.itens_enquadrados,
            'circunstancias': patd.circunstancias,
            'punicao': patd.punicao_sugerida,
        }
    except Exception as exc:
        logger.error("analisar_punicao_task falhou (pk=%s): %s", patd_pk, exc, exc_info=True)
        _retry_task(self, exc, patd_pk, "analisar_punicao_task")
