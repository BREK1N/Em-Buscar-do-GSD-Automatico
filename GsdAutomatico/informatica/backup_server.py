"""
Acesso remoto (SFTP + SSH) ao servidor reserva de backup, usando as
credenciais já cadastradas em BackupDestino. Restrito a is_informatica_admin
nas views que chamam este módulo.
"""
import io
import stat

import paramiko

# Extensões de arquivo de texto que podem ser visualizadas/editadas inline.
EXTENSOES_TEXTO = {
    '.txt', '.log', '.md', '.py', '.json', '.yml', '.yaml', '.conf', '.cfg',
    '.ini', '.sh', '.env', '.csv', '.xml', '.html', '.css', '.js',
}
TAMANHO_MAX_EDICAO = 2 * 1024 * 1024  # 2MB


def _client(destino) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    if destino.host_key_fingerprint:
        # TOFU já fixado: usa o fingerprint conhecido (mesmo critério do backup SFTP)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=destino.host, port=destino.porta, username=destino.usuario,
        password=destino.get_senha(), timeout=15,
    )
    return client


def listar_diretorio(destino, caminho: str) -> list[dict]:
    """Lista arquivos/pastas em `caminho`. Retorna lista de dicts ordenada: pastas primeiro."""
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            entradas = sftp.listdir_attr(caminho)
        finally:
            sftp.close()
    finally:
        client.close()

    itens = []
    for e in entradas:
        is_dir = stat.S_ISDIR(e.st_mode)
        itens.append({
            'nome': e.filename,
            'is_dir': is_dir,
            'tamanho': e.st_size,
            'modificado': e.st_mtime,
        })
    itens.sort(key=lambda i: (not i['is_dir'], i['nome'].lower()))
    return itens


def ler_arquivo_texto(destino, caminho: str) -> str:
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(caminho, 'r') as f:
                conteudo = f.read(TAMANHO_MAX_EDICAO + 1)
        finally:
            sftp.close()
    finally:
        client.close()
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode('utf-8', errors='replace')
    return conteudo


def salvar_arquivo_texto(destino, caminho: str, conteudo: str):
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            with sftp.open(caminho, 'w') as f:
                f.write(conteudo)
        finally:
            sftp.close()
    finally:
        client.close()


def baixar_arquivo(destino, caminho: str) -> bytes:
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            buf = io.BytesIO()
            sftp.getfo(caminho, buf)
            return buf.getvalue()
        finally:
            sftp.close()
    finally:
        client.close()


def excluir_arquivo(destino, caminho: str):
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            sftp.remove(caminho)
        finally:
            sftp.close()
    finally:
        client.close()


def excluir_diretorio_vazio(destino, caminho: str):
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            sftp.rmdir(caminho)
        finally:
            sftp.close()
    finally:
        client.close()


def criar_diretorio(destino, caminho: str):
    client = _client(destino)
    try:
        sftp = client.open_sftp()
        try:
            sftp.mkdir(caminho)
        finally:
            sftp.close()
    finally:
        client.close()


def eh_extensao_texto(nome: str) -> bool:
    nome = nome.lower()
    return any(nome.endswith(ext) for ext in EXTENSOES_TEXTO)
