#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv

def main():
    load_dotenv()

    # Pega as variáveis de proxy do ambiente
    # proxy_user = os.getenv("PROXY_USER")
    # proxy_password = os.getenv("PROXY_PASSWORD")
    # proxy_port = os.getenv("PROXY_PORT")
    # proxy_address = "10.52.132.240"

    # Se todas as variáveis de proxy existirem, configura o ambiente
    # if all([proxy_user, proxy_password, proxy_port]):
    #     proxy_url = f"http://{proxy_user}:{proxy_password}@{proxy_address}:{proxy_port}"
    #     os.environ['HTTP_PROXY'] = proxy_url
    #     os.environ['HTTPS_PROXY'] = proxy_url
    #     print(">>> Variaveis de ambiente do proxy configuradas com sucesso.")


    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GsdAutomatico.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
