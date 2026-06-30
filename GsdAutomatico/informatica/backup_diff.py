"""
Restauração/comparação de registros individuais a partir de um backup antigo.

Funciona restaurando o dump (.dump, formato pg_dump -F c) escolhido em um banco
Postgres temporário isolado (via pg_restore), consultando o registro desejado
por SQL bruto (psycopg2) e comparando campo a campo com o registro atual no
banco em produção — sem nunca tocar o banco em produção até o admin confirmar
a restauração de um registro específico.
"""
import subprocess
import uuid

import psycopg2
from django.conf import settings

from Ouvidoria.models import PATD
from Secao_pessoal.models import Efetivo
from Secao_operacoes.models import Missao, Escala
from EPA.models import EscalaMissaoEPA
from caixa_entrada.models import Mensagem
from .models import Material, Cautela

# Modelos disponíveis para comparação/restauração individual.
# 'colunas_lista': colunas exibidas na listagem do backup — (campo_db, label, tipo)
#   tipo: 'text' | 'date' | 'status_patd' | 'bool_sim_nao' | 'bool_lixeira'
# 'campos_destaque': campos exibidos em destaque no topo da visualização individual
MODELOS_DIFF = {
    'patd': {
        'label': 'PATD (Ouvidoria)',
        'model': PATD,
        'busca_campo': 'numero_patd',
        'colunas_lista': [
            ('numero_patd',  'Nº PATD',      'text'),
            ('militar_id',   'Militar (ID)',  'text'),
            ('status',       'Status',        'status_patd'),
            ('arquivado',    'Arquivado',     'bool_sim_nao'),
            ('deleted',      'Lixeira',       'bool_lixeira'),
            ('data_inicio',  'Abertura',      'date'),
        ],
        'campos_destaque': ['transgressao', 'punicao', 'alegacao_defesa', 'comportamento', 'natureza_transgressao'],
    },
    'efetivo': {
        'label': 'Efetivo (Secção de Pessoal)',
        'model': Efetivo,
        'busca_campo': 'nome_completo',
        'colunas_lista': [
            ('nome_completo', 'Nome Completo', 'text'),
            ('nome_guerra',   'Nome de Guerra','text'),
            ('posto',         'Posto/Grad.',   'text'),
            ('situacao',      'Situação',      'text'),
            ('om',            'OM',            'text'),
            ('deleted',       'Lixeira',       'bool_lixeira'),
        ],
        'campos_destaque': ['posto', 'nome_guerra', 'situacao', 'setor', 'om'],
    },
    'missao': {
        'label': 'Missão / OMIS (Secção de Operações)',
        'model': Missao,
        'busca_campo': 'numero',
        'colunas_lista': [
            ('numero',      'Número',   'text'),
            ('nome_missao', 'Nome',     'text'),
            ('data_missao', 'Data',     'date'),
            ('local',       'Local',    'text'),
        ],
        'campos_destaque': ['nome_missao', 'local', 'data_missao'],
    },
    'escala_servico': {
        'label': 'Escala de Serviço (Secção de Operações)',
        'model': Escala,
        'busca_campo': 'tipo',
        'colunas_lista': [
            ('tipo',    'Tipo',   'text'),
            ('ativo',   'Ativo',  'bool_sim_nao'),
        ],
        'campos_destaque': ['tipo', 'duracao_horas'],
    },
    'escala_epa': {
        'label': 'Escala EPA (Esquadrão de Polícia da Aeronáutica)',
        'model': EscalaMissaoEPA,
        'busca_campo': 'identificacao_pelotao',
        'colunas_lista': [
            ('identificacao_pelotao', 'Pelotão', 'text'),
            ('observacoes',           'Obs.',    'text'),
        ],
        'campos_destaque': ['identificacao_pelotao', 'observacoes'],
    },
    'mensagem': {
        'label': 'Mensagem / Chamado (Caixa de Entrada)',
        'model': Mensagem,
        'busca_campo': 'assunto',
        'colunas_lista': [
            ('assunto',        'Assunto',       'text'),
            ('status_chamado', 'Status',        'text'),
        ],
        'campos_destaque': ['assunto', 'status_chamado'],
    },
    'material': {
        'label': 'Material (Informática)',
        'model': Material,
        'busca_campo': 'nome',
        'colunas_lista': [
            ('nome',                  'Nome',        'text'),
            ('quantidade',            'Qtd.',        'text'),
            ('funcionando',           'Funcionando', 'bool_sim_nao'),
        ],
        'campos_destaque': ['nome', 'quantidade', 'funcionando'],
    },
    'cautela': {
        'label': 'Cautela (Informática)',
        'model': Cautela,
        'busca_campo': 'nome_missao',
        'colunas_lista': [
            ('nome_missao', 'Missão',  'text'),
            ('ativa',       'Ativa',   'bool_sim_nao'),
        ],
        'campos_destaque': ['nome_missao', 'ativa'],
    },
}

# Labels legíveis para os status da PATD
PATD_STATUS_LABELS = {
    'definicao_oficial':              'Aguardando Oficial',
    'aguardando_aprovacao_atribuicao':'Aguardando Aprovação',
    'confeccao_fr_ficha':             'Confecção FR/Ficha',
    'ciencia_militar':                'Aguardando Ciência',
    'aguardando_justificativa':       'Aguardando Justificativa',
    'prazo_expirado':                 'Prazo Expirado',
    'preclusao':                      'Preclusão',
    'em_apuracao':                    'Em Apuração',
    'apuracao_preclusao':             'Apuração (Preclusão)',
    'aguardando_punicao':             'Aguardando Punição',
    'aguardando_punicao_alterar':     'Aguardando Punição (alterar)',
    'analise_oficial_apurador':       'Análise Oficial Apurador',
    'analise_comandante':             'Análise Comandante',
    'aguardando_assinatura_npd':      'Aguardando Assinatura NPD',
    'periodo_reconsideracao':         'Período de Reconsideração',
    'em_reconsideracao':              'Em Reconsideração',
    'aguardando_nova_punicao':        'Aguardando Nova Punição',
    'aguardando_publicacao':          'Aguardando Publicação',
    'finalizado':                     'Finalizado',
}

# Campos que nunca devem ser comparados/restaurados: chave técnica ou dado sensível
# (credencial/segredo) que não deve aparecer em texto puro numa tela de diff.
CAMPOS_IGNORADOS = {'id', 'senha_unica', 'senha_criptografada', 'password'}


def _db_conf():
    return settings.DATABASES['default']


def buscar_registro_atual(model, busca_campo: str, valor: str):
    """Localiza o registro atual: tenta por id (se o valor for numérico) e cai para busca_campo."""
    if valor.isdigit():
        obj = model.objects.filter(pk=int(valor)).first()
        if obj:
            return obj
    return model.objects.filter(**{busca_campo: valor}).first()


def restaurar_dump_temp(arquivo_db: str) -> str:
    """Cria um banco Postgres temporário e restaura o dump dentro dele. Retorna o nome do banco."""
    db_conf = _db_conf()
    tempdb = f"restore_tmp_{uuid.uuid4().hex[:12]}"

    import os
    env = os.environ.copy()
    env['PGPASSWORD'] = db_conf['PASSWORD'] or ''

    subprocess.run(
        ['createdb', '-h', db_conf['HOST'], '-p', str(db_conf['PORT']), '-U', db_conf['USER'], tempdb],
        env=env, check=True, capture_output=True, text=True, timeout=60,
    )
    subprocess.run(
        ['pg_restore', '-h', db_conf['HOST'], '-p', str(db_conf['PORT']), '-U', db_conf['USER'],
         '-d', tempdb, '--no-owner', '--no-privileges', arquivo_db],
        env=env, check=False, capture_output=True, text=True, timeout=280,
        # check=False: pg_restore retorna != 0 com avisos não-fatais (ex.: extensões já existentes)
    )
    return tempdb


def dropar_temp(tempdb: str):
    db_conf = _db_conf()
    import os
    env = os.environ.copy()
    env['PGPASSWORD'] = db_conf['PASSWORD'] or ''
    subprocess.run(
        ['dropdb', '--if-exists', '-h', db_conf['HOST'], '-p', str(db_conf['PORT']), '-U', db_conf['USER'], tempdb],
        env=env, check=False, capture_output=True, text=True, timeout=60,
    )


def _conectar_temp(tempdb: str):
    db_conf = _db_conf()
    return psycopg2.connect(
        host=db_conf['HOST'], port=db_conf['PORT'], user=db_conf['USER'],
        password=db_conf['PASSWORD'], dbname=tempdb,
    )


def buscar_registro_temp(tempdb: str, model, pk: int) -> dict | None:
    """Busca o registro pelo id na tabela correspondente do banco temporário restaurado."""
    tabela = model._meta.db_table
    conn = _conectar_temp(tempdb)
    try:
        with conn.cursor() as cur:
            # Aspas duplas obrigatórias: db_table tem maiúsculas (ex: Ouvidoria_patd)
            cur.execute(f'SELECT * FROM "{tabela}" WHERE id = %s', [pk])
            row = cur.fetchone()
            if row is None:
                return None
            colunas = [c.name for c in cur.description]
            return dict(zip(colunas, row))
    finally:
        conn.close()


def listar_todos_temp(tempdb: str, model, limit: int = 500) -> list[dict]:
    """Retorna todos os registros da tabela no banco temporário, até `limit` linhas."""
    tabela = model._meta.db_table
    conn = _conectar_temp(tempdb)
    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT * FROM "{tabela}" ORDER BY id LIMIT %s', [limit])
            rows = cur.fetchall()
            if not rows:
                return []
            colunas = [c.name for c in cur.description]
            return [dict(zip(colunas, row)) for row in rows]
    finally:
        conn.close()


def campos_comparaveis(model):
    """Campos simples do model (exclui reverse relations e M2M, que não existem como coluna)."""
    campos = []
    for f in model._meta.fields:
        if f.name in CAMPOS_IGNORADOS:
            continue
        campos.append(f)
    return campos


def montar_diff(old_dict: dict, live_obj) -> list:
    """Compara cada campo do registro antigo (dict de colunas do dump) com o objeto atual."""
    model = type(live_obj)
    diffs = []
    for f in campos_comparaveis(model):
        coluna = f.column
        if coluna not in old_dict:
            continue
        valor_antigo = old_dict[coluna]
        valor_atual = getattr(live_obj, f.attname)
        diferente = str(valor_antigo) != str(valor_atual)
        diffs.append({
            'campo': f.name,
            'label': f.verbose_name if hasattr(f, 'verbose_name') else f.name,
            'antigo': valor_antigo,
            'atual': valor_atual,
            'diferente': diferente,
        })
    return diffs


def aplicar_restore(live_obj, old_dict: dict, campos_selecionados: list):
    """Aplica, no registro em produção, os valores antigos apenas dos campos selecionados."""
    model = type(live_obj)
    alterados = []
    for f in campos_comparaveis(model):
        if f.name not in campos_selecionados:
            continue
        if f.column not in old_dict:
            continue
        novo_valor = old_dict[f.column]
        if getattr(live_obj, f.attname) != novo_valor:
            setattr(live_obj, f.attname, novo_valor)
            alterados.append(f.name)
    if alterados:
        live_obj.save()
    return alterados
