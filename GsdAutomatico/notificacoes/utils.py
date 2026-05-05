import logging
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def notificar(usuario, titulo: str, *, corpo: str = '', url: str = '',
              tipo: str = 'sistema', origem_id: int = None, origem_tipo: str = '') -> None:
    """
    Cria uma ou mais Notificacao para o(s) usuário(s) informados.
    Nunca lança exceção — falhas são logadas silenciosamente.

    Uso:
        notificar(user, "Título", corpo="...", url="/path/", tipo='mensagem')
        notificar(User.objects.filter(groups__name='Ouvidoria'), "Aviso", tipo='patd')
    """
    from .models import Notificacao

    if usuario is None:
        return

    if isinstance(usuario, User):
        usuarios = [usuario]
    else:
        try:
            usuarios = list(usuario)
        except TypeError:
            usuarios = [usuario]

    objs = [
        Notificacao(
            usuario=u,
            tipo=tipo,
            titulo=str(titulo)[:255],
            corpo=corpo,
            url=url,
            origem_id=origem_id,
            origem_tipo=origem_tipo,
        )
        for u in usuarios if u is not None
    ]

    if not objs:
        return

    try:
        Notificacao.objects.bulk_create(objs)
    except Exception as exc:
        logger.exception("notificar() falhou: %s", exc)
