import logging
import time

logger = logging.getLogger('django')

class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Lista de termos que, se estiverem na URL, cancelam o log
        self.ignored_paths = [
            '/static/', 
            '/media/', 
            '/favicon.ico', 
            '/api/logs/',          # Filtra a API de logs
            'jsi18n',              # Filtra traduções de JS do admin
        ]

    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        
        # Verifica se QUALQUER termo ignorado está presente no caminho da URL
        # Isso resolve o problema de '/informatica/api/logs/' não ser pego pelo startswith
        should_ignore = any(term in request.path for term in self.ignored_paths)

        # Só loga se não for um caminho ignorado
        if not should_ignore:
            user = getattr(request, 'user', None)
            user_id = 'Anon'
            if user and user.is_authenticated:
                user_id = f'{user.username}'

            status_code = response.status_code
            method = request.method
            path = request.path
            
            # Formatação limpa para o terminal
            log_msg = f"[{method}] {path} | User: {user_id} | Status: {status_code} | {duration:.2f}s"
            
            if status_code >= 500:
                logger.error(f"❌ {log_msg}")
            elif status_code >= 400:
                logger.warning(f"⚠️ {log_msg}")
            else:
                logger.info(f"ℹ️ {log_msg}")

        return response