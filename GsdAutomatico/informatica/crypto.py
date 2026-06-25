import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _get_fernet():
    # Deriva uma chave Fernet (32 bytes, urlsafe-base64) a partir da SECRET_KEY do projeto,
    # já que SECRET_KEY não tem o formato exigido pelo Fernet diretamente.
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_text(plain: str) -> str:
    if not plain:
        return ''
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_text(token: str) -> str:
    if not token:
        return ''
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ''
