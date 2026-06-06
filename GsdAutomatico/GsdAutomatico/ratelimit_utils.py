"""
Utilitários de rate limiting compatíveis com django-ratelimit 4.1.0.

O 4.1.0 não tem RATELIMIT_SKIP_IF. O bypass é feito via função de key:
retornar None cancela o rate limit para aquela request.
"""
import ipaddress

# Redes isentas: loopback + RFC-1918 (rede interna da OM e containers Docker)
_EXEMPT_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def _get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    return xff or request.META.get("REMOTE_ADDR", "")


def _is_local(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _EXEMPT_NETWORKS)
    except ValueError:
        return False


def rate_if_external(group, request):
    """
    Rate function para @ratelimit(rate=...): retorna None (sem limite) para
    IPs internos/locais, ou a rate normal para IPs externos.

    Uso: @ratelimit(key='ip', rate=rate_if_external, method='POST', block=True)

    No django-ratelimit 4.1.0, quando `rate` é um callable que retorna None,
    get_usage() retorna None e a request não é limitada.
    """
    ip = _get_client_ip(request)
    if _is_local(ip):
        return None   # bypass: get_usage() retorna None → não limitado
    return '10/m'
