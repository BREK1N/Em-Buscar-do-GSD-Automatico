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

# Modelos disponíveis para comparação/restauração individual — uma entrada por seção.
# 'busca_campo' é o campo usado para localizar o registro pelo usuário (além do id).
MODELOS_DIFF = {
    'patd': {
        'label': 'PATD (Ouvidoria)',
        'model': PATD,
        'busca_campo': 'numero_patd',
    },
    'efetivo': {
        'label': 'Efetivo (Secção de Pessoal)',
        'model': Efetivo,
        'busca_campo': 'nome_completo',
    },
    'missao': {
        'label': 'Missão / OMIS (Secção de Operações)',
        'model': Missao,
        'busca_campo': 'numero',
    },
    'escala_servico': {
        'label': 'Escala de Serviço (Secção de Operações)',
        'model': Escala,
        'busca_campo': 'nome',
    },
    'escala_epa': {
        'label': 'Escala EPA (Esquadrão de Polícia da Aeronáutica)',
        'model': EscalaMissaoEPA,
        'busca_campo': 'missao__numero',
    },
    'mensagem': {
        'label': 'Mensagem / Chamado (Caixa de Entrada)',
        'model': Mensagem,
        'busca_campo': 'assunto',
    },
    'material': {
        'label': 'Material (Informática)',
        'model': Material,
        'busca_campo': 'nome',
    },
    'cautela': {
        'label': 'Cautela (Informática)',
        'model': Cautela,
        'busca_campo': 'nome_missao',
    },
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
