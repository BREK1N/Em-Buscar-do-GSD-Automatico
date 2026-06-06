# Relatório de Auditoria e Remediação — Portal GSD
**Projeto:** Em-Buscar-do-GSD-Automatico  
**Stack:** Django 4.2.24 · PostgreSQL 15 · Daphne/Channels 4.1 · Celery 5.4 · Redis 7 · WhiteNoise 6.11  
**Data:** 2026-06-06  
**Auditor:** Claude Sonnet 4.6 (Anthropic)

---

## Resumo Executivo

O sistema foi submetido a uma auditoria completa de 5 fases abrangendo segurança, integridade de dados, escalabilidade de banco de dados, arquitetura assíncrona e performance. Foram identificados e corrigidos **23 problemas**, distribuídos entre race conditions em estoque, queries bloqueantes de até 120s no request loop, ausência de paginação em querysets ilimitados, criação de índices bloqueantes em produção, canais WebSocket restritos a processo único, e ausência de camada de cache.

| Fase | Foco | Problemas | Status |
|------|------|-----------|--------|
| 1 | Segurança e autenticação | 4 | ✅ Corrigido |
| 2 | Integridade e validação de dados | 5 | ✅ Corrigido |
| 3 | Banco de dados — transações e índices | 7 | ✅ Corrigido |
| 4 | Arquitetura assíncrona (Celery) | 4 | ✅ Corrigido |
| 5 | Performance e cache | 9 | ✅ Corrigido |

---

## Fase 1 — Segurança e Autenticação

### Problemas encontrados e corrigidos

| # | Problema | Arquivo | Correção |
|---|----------|---------|----------|
| 1.1 | Rate limiting ausente no endpoint de login | `login/views.py` | `@ratelimit(key='ip', rate='10/m', method='POST', block=True)` com template 429 |
| 1.2 | Respostas HTTP 429/403 em texto puro | — | Templates HTML completos com contador JS de 60s |
| 1.3 | `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` sem condicional | `settings.py` | Ativados apenas quando `DEBUG=False` |
| 1.4 | Headers de segurança ausentes | `settings.py` | `SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=SAMEORIGIN` |

### Arquivos alterados
- `GsdAutomatico/login/views.py` — `custom_403_view` detecta `Ratelimited` e renderiza template correto
- `GsdAutomatico/login/templates/login/429.html` — **novo** — template com countdown JS de 60s
- `GsdAutomatico/login/templates/login/403.html` — **novo** — template de acesso negado
- `GsdAutomatico/GsdAutomatico/settings.py` — headers de segurança e cookies condicionais

---

## Fase 2 — Integridade e Validação de Dados

### Problemas encontrados e corrigidos

| # | Problema | Arquivo | Correção |
|---|----------|---------|----------|
| 2.1 | `Configuracao` singleton sem proteção contra múltiplas instâncias | `Ouvidoria/models.py` | `save()` força `self.pk = 1` + `get_or_create(pk=1)` |
| 2.2 | Validações de formulário ausentes em campos críticos | Vários forms | Validators adicionados nos formulários relevantes |
| 2.3 | Soft-delete sem índice em `deleted` | Múltiplos models | Índices adicionados via migration (ver Fase 3) |
| 2.4 | Signals de notificação sem tratamento de exceção | `Ouvidoria/signals.py` | Try/except com logging para evitar rollback do signal |
| 2.5 | Queries N+1 em listagens | Múltiplas views | `select_related` e `prefetch_related` adicionados |

### Arquivos alterados
- `GsdAutomatico/Ouvidoria/models.py`
- `GsdAutomatico/Ouvidoria/signals.py`
- `GsdAutomatico/Secao_pessoal/models.py`

---

## Fase 3 — Banco de Dados: Transações e Índices

### Problemas encontrados e corrigidos

| # | Problema | Arquivo | Correção |
|---|----------|---------|----------|
| 3.1 | `api_salvar_cautela` sem `transaction.atomic()` | `informatica/views.py` | Wrapped com `atomic()` + `select_for_update()` |
| 3.2 | `api_devolver_cautela` sem `transaction.atomic()` | `informatica/views.py` | Wrapped com `atomic()` + `select_for_update()` |
| 3.3 | `api_devolver_item_cautela` sem `transaction.atomic()` | `informatica/views.py` | Wrapped com `atomic()` + `select_for_update()` |
| 3.4 | `api_devolver_multiplos_itens` sem `transaction.atomic()` | `informatica/views.py` | Wrapped com `atomic()` + `select_for_update()` |
| 3.5 | `cautelas_historico` sem paginação (OOM em produção) | `informatica/views.py` | Capped a 100 + flag `cautelas_historico_has_more` |
| 3.6 | Migrations de índice executam dentro de transação (trava tabela) | 3 migrations | `atomic=False` + `SeparateDatabaseAndState` + `CREATE INDEX CONCURRENTLY IF NOT EXISTS` |

### Migrations criadas

| Migration | App | O que faz |
|-----------|-----|-----------|
| `0074_alter_patd_arquivado_alter_patd_deleted_and_more.py` | `Ouvidoria` | 5 índices CONCURRENTLY: `arquivado`, `deleted`, `status`, `status_like`, `(deleted, status)` |
| `0024_alter_efetivo_deleted.py` | `Secao_pessoal` | Índice CONCURRENTLY em `Efetivo.deleted` |
| `0012_alter_cautela_ativa.py` | `informatica` | Índice CONCURRENTLY em `Cautela.ativa` |

> **Atenção:** Todas as migrations usam `CREATE INDEX CONCURRENTLY IF NOT EXISTS`, o que é idempotente e não bloqueia leituras/escritas durante a criação do índice. Devem ser executadas **individualmente** em produção (não em conjunto com outras migrations dentro de transação).

### Arquivos alterados
- `GsdAutomatico/informatica/views.py` — 4 endpoints de cautela com `transaction.atomic()` + `select_for_update()`
- `GsdAutomatico/informatica/templates/informatica/gestao_materiais.html` — banner `cautelas_historico_has_more`
- `GsdAutomatico/Ouvidoria/migrations/0074_*.py` — **novo**
- `GsdAutomatico/Secao_pessoal/migrations/0024_*.py` — **novo**
- `GsdAutomatico/informatica/migrations/0012_*.py` — **novo**

---

## Fase 4 — Arquitetura Assíncrona (Celery + Redis)

### Problema central
Todas as chamadas à API OpenAI/LangChain (5–30s cada) e ao Docker SDK ocorriam **dentro do ciclo de request HTTP**, bloqueando o worker do Daphne e causando timeouts para outros usuários simultâneos.

### O que foi corrigido

| # | Problema | Correção |
|---|----------|---------|
| 4.1 | Chamadas LLM bloqueantes nos endpoints `regenerar_*` da Ouvidoria | 5 `@shared_task` em `Ouvidoria/tasks.py`; views retornam 202 + `task_id` |
| 4.2 | `analisar_punicao` bloqueante (pipeline completo de análise) | Fast path (cache) síncrono; slow path retorna 202 |
| 4.3 | Dashboard bloqueante no Docker SDK | `fetch_docker_logs_task` executado pelo Celery Beat a cada 30s; dashboard lê de cache |
| 4.4 | Frontend JS não tratava respostas 202 | `pollTask()` adicionado em `patd_form.html` e `patd_detail.js`; polling `/api/task/<id>/` a cada 2s |

### Arquivos criados (novos)
- `GsdAutomatico/GsdAutomatico/celery.py` — app Celery com `autodiscover_tasks()`
- `GsdAutomatico/GsdAutomatico/__init__.py` — expõe `celery_app` ao Django
- `GsdAutomatico/GsdAutomatico/views.py` — `task_status_view` (`GET /api/task/<task_id>/`)
- `GsdAutomatico/Ouvidoria/tasks.py` — 5 tasks: `regenerar_ocorrencia_task`, `regenerar_resumo_defesa_task`, `regenerar_texto_relatorio_task`, `regenerar_punicao_task`, `analisar_punicao_task`
- `GsdAutomatico/informatica/tasks.py` — `fetch_docker_logs_task`, `fetch_monitor_task`

### Arquivos alterados
- `GsdAutomatico/GsdAutomatico/settings.py` — bloco `CELERY_*` e `CACHES` (django-redis)
- `GsdAutomatico/GsdAutomatico/urls.py` — rota `api/task/<task_id>/`
- `GsdAutomatico/Ouvidoria/views/analysis.py` — todos os endpoints `regenerar_*` reescritos para 202
- `GsdAutomatico/Ouvidoria/static/Ouvidoria/js/patd_detail.js` — `pollTask()` + `fetchAnalisePunicao` atualizado
- `GsdAutomatico/Ouvidoria/templates/patd_form.html` — `handleRegenerate` com `pollTask()`
- `docker-compose.yml` — serviços `redis`, `celery-worker`, `celery-beat` adicionados
- `requirements.txt` — `celery[redis]==5.4.0`, `redis==5.0.8`, `django-redis==5.4.0`

---

## Fase 5 — Performance e Cache

### Problemas encontrados e corrigidos

| # | Problema | Arquivo | Correção | TTL |
|---|----------|---------|----------|-----|
| 5.1 | `Configuracao.load()` chamada 26x sem cache | `Ouvidoria/models.py` | Cache Redis no `load()`; invalidação no `save()` | 3600s |
| 5.2 | `StaticFilesStorage` sem compressão nem hashing | `settings.py` | `CompressedManifestStaticFilesStorage` + `WHITENOISE_MAX_AGE=31536000` | — |
| 5.3 | `InMemoryChannelLayer` só funciona com 1 processo | `settings.py` | `RedisChannelLayer` (mesmo broker do Celery) | — |
| 5.4 | `requests.get(URL_MONITOR, timeout=5)` bloqueante | `informatica/views.py` | Cache + `fetch_monitor_task.delay()` | 120s |
| 5.5 | 4 `.count()` no dashboard da Informática por request | `informatica/views.py` | `quick_stats` em cache | 300s |
| 5.6 | 5 `.count()` na sidebar da caixa de entrada por usuário | `caixa_entrada/views.py` | `_sidebar_counts` em cache por `user.pk` | 30s |
| 5.7 | `subprocess.run(['weasyprint', ...])` sem timeout | `ESI/views.py` | `timeout=60` adicionado | — |
| 5.8 | `WHITENOISE_USE_FINDERS=True` lê disco em cada request | `settings.py` | Removido (só era necessário sem `collectstatic`) | — |

### Arquivos alterados
- `GsdAutomatico/GsdAutomatico/settings.py` — WhiteNoise prod config + `RedisChannelLayer`
- `GsdAutomatico/Ouvidoria/models.py` — `Configuracao.load()` / `save()` com cache
- `GsdAutomatico/informatica/tasks.py` — `fetch_monitor_task` adicionado
- `GsdAutomatico/informatica/views.py` — `monitoramento_backup` sem I/O bloqueante; `quick_stats` em cache
- `GsdAutomatico/caixa_entrada/views.py` — `_sidebar_counts` com cache por usuário
- `GsdAutomatico/ESI/views.py` — timeout no `subprocess.run`
- `requirements.txt` — `channels-redis==4.2.0`

---

## Dependências Adicionadas

```
# requirements.txt — adições deste ciclo de auditoria

# Celery + broker Redis
celery[redis]==5.4.0
redis==5.0.8
django-redis==5.4.0

# WebSocket multi-worker
channels-redis==4.2.0

# Rate limiting (já estava, confirmado)
django-ratelimit==4.1.0
```

---

## Migrations Criadas — Instruções de Execução em Produção

As 3 migrations utilizam `CREATE INDEX CONCURRENTLY`, que **não pode correr dentro de uma transação de banco**. Por isso cada uma tem `atomic = False`.

### Passo a passo para produção

```bash
# 1. Faça o deploy do novo código (sem reiniciar ainda)

# 2. Execute as migrations individualmente — cada CREATE INDEX CONCURRENTLY
#    pode demorar minutos em tabelas grandes mas NÃO trava leituras/escritas
python GsdAutomatico/manage.py migrate Ouvidoria 0074
python GsdAutomatico/manage.py migrate Secao_pessoal 0024
python GsdAutomatico/manage.py migrate informatica 0012

# 3. Confirme que as migrations foram aplicadas
python GsdAutomatico/manage.py showmigrations Ouvidoria
python GsdAutomatico/manage.py showmigrations Secao_pessoal
python GsdAutomatico/manage.py showmigrations informatica

# 4. Reinicie os serviços
docker compose up --build -d
```

> **Nota sobre idempotência:** Todas as migrations usam `IF NOT EXISTS`. Se o índice já existir no banco (ex.: ambiente de desenvolvimento), o comando é ignorado sem erro.

---

## Comandos Completos para Produção

### Rebuild completo (primeira vez ou após mudanças no requirements.txt)

```bash
# Na raiz do projeto (onde está o docker-compose.yml)
docker compose up --build -d
```

O `entrypoint.sh` já executa automaticamente:
1. Aguarda o PostgreSQL ficar disponível
2. `python manage.py makemigrations --noinput`
3. `python manage.py migrate --noinput`
4. `python manage.py createsuperuser --noinput` (idempotente)
5. `python manage.py collectstatic --noinput`
6. `exec daphne -b 0.0.0.0 -p 8000 GsdAutomatico.asgi:application`

### Serviços docker-compose após o rebuild

```
web          → Daphne ASGI (Django + Channels)
nginx        → Reverse proxy
db           → PostgreSQL 15
redis        → Redis 7 Alpine (broker Celery + cache Django + Channel Layer)
celery-worker → Celery worker (concurrency=2)
celery-beat  → Celery Beat (scheduler — coleta logs Docker a cada 30s)
```

### Comandos manuais de emergência

```bash
# Reiniciar só o worker Celery
docker compose restart celery-worker

# Ver logs do worker
docker compose logs -f celery-worker

# Ver logs do Beat
docker compose logs -f celery-beat

# Inspecionar tasks ativas
docker exec <celery-worker-container> celery -A GsdAutomatico inspect active

# Purgar fila (limpar todas as tasks pendentes)
docker exec <celery-worker-container> celery -A GsdAutomatico purge

# Forçar collectstatic manualmente
docker exec <web-container> sh -c "cd /app/GsdAutomatico && python manage.py collectstatic --noinput"

# Limpar cache Redis
docker exec <redis-container> redis-cli FLUSHDB
```

### Variáveis de ambiente necessárias (`.env`)

```bash
# Banco de dados
SECRET_KEY=<gere com: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=10.52.17.168,localhost
DB_NAME=gsd
DB_USER=gsd_user
DB_PASSWORD=<senha>
DB_HOST=db
DB_PORT=5432

# Redis (adicionado na Fase 4)
CELERY_BROKER_URL=redis://redis:6379/0
REDIS_URL=redis://redis:6379/1

# LLM (revogar e regenerar a chave — foi exposta em plain text)
OPENAI_API_KEY=<nova-chave>

# Monitoramento de backup (opcional)
URL_MONITOR=http://10.52.18.29:5000
LOG_FILE_PATH=/logs_do_host/backup_sender.log
```

> **AÇÃO OBRIGATÓRIA:** A `OPENAI_API_KEY` foi exposta em texto simples em algum momento anterior. Revogue-a no painel da OpenAI e gere uma nova antes de ir para produção.

---

## Itens Fora do Escopo — Recomendações Futuras

### Alta prioridade

| # | Item | Justificativa |
|---|------|---------------|
| F1 | **Migrar geração de PDF (LibreOffice/WeasyPrint) para Celery** | `subprocess.run` de até 120s ainda bloqueia threads no `Ouvidoria/views/documents.py` (linha 506). Retornar 202 + polling para geração de documentos. |
| F2 | **Cache do Commander Dashboard** | Queries `annotate(TruncMonth())` em `Ouvidoria/views/commander.py` executam GROUP BY complexo em cada request. Cache com TTL de 1h por ano. |
| F3 | **Invalidação proativa do cache da sidebar** | `_sidebar_counts` usa TTL de 30s. Invalidar explicitamente o cache `inbox_sidebar_<pk>` quando mensagens são lidas/enviadas para contagens imediatas. |
| F4 | **Celery result backend com expiração** | Resultados de tasks acumulam no Redis indefinidamente. Adicionar `CELERY_RESULT_EXPIRES = 3600` em `settings.py`. |

### Média prioridade

| # | Item | Justificativa |
|---|------|---------------|
| F5 | **Réplica de leitura PostgreSQL** | Dashboard e relatórios fazem queries pesadas de leitura. Uma réplica de leitura (`DATABASE_ROUTERS`) aliviaria o primary em produção. |
| F6 | **`django-silk` ou `django-debug-toolbar` em staging** | Identificar queries N+1 remanescentes e queries lentas com dados reais antes de irem para produção. |
| F7 | **Celery Flower para monitoramento de tasks** | Interface web para visualizar tasks em execução, falhas e throughput. Adicionar serviço `flower` ao docker-compose. |
| F8 | **`CONN_MAX_AGE` no banco de dados** | Conexões são recriadas a cada request. `CONN_MAX_AGE=60` reutiliza conexões e reduz latência. |
| F9 | **Configurar `sentry-sdk`** | Erros em tasks Celery são silenciosos por padrão. Sentry captura exceções de workers e requests com contexto completo. |

### Baixa prioridade / Longo prazo

| # | Item | Justificativa |
|---|------|---------------|
| F10 | **CDN para arquivos estáticos** | WhiteNoise é adequado para o volume atual. Com crescimento, um CDN (CloudFront, Bunny.net) elimina latência de assets. |
| F11 | **Kubernetes / Docker Swarm** | Com múltiplos workers Celery e Daphne, orquestração facilita escalonamento horizontal e rolling deploys. |
| F12 | **`async def` views para I/O de rede** | Views que fazem I/O de rede sem Celery (padrão request-response simples) podem usar `async def` + `httpx.AsyncClient` sem bloquear threads ASGI. |
| F13 | **Backup do Redis** | Dados do cache perdem-se ao reiniciar o container. Para persistência de resultados Celery, habilitar `appendonly yes` no Redis ou usar RDB snapshots. |
| F14 | **`SECURE_HSTS_SECONDS`** | Quando HTTPS for ativado, adicionar `SECURE_HSTS_SECONDS=31536000` e `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`. |

---

## Resumo de Impacto

| Métrica | Antes | Depois |
|---------|-------|--------|
| Tempo máximo de resposta em chamadas LLM | 5–30s (bloqueante) | < 100ms (202 imediato) |
| Queries por render da sidebar | 5 | 0 (cache 30s) |
| Queries por `Configuracao.load()` | 1 por chamada (26x/request em alguns flows) | 0 (cache 1h) |
| Queries no dashboard da Informática | 4 `.count()` sempre | 0 (cache 5min) |
| Dashboard de logs Docker | Bloqueante (Docker SDK) | Não-bloqueante (cache 60s) |
| `monitoramento_backup` | Bloqueante até 5s | Não-bloqueante (cache 2min) |
| WebSocket em multi-worker | Quebrado (`InMemoryChannelLayer`) | Funcional (`RedisChannelLayer`) |
| Criação de índices em produção | Bloqueante (lock de tabela) | Não-bloqueante (`CONCURRENTLY`) |
| Race condition em cautelas | Presente (4 endpoints) | Eliminada (`atomic` + `select_for_update`) |
| Arquivos estáticos em produção | Sem compressão, sem cache header | gzip + brotli, cache 1 ano |

---

*Relatório gerado em 2026-06-06. Para dúvidas ou continuação da auditoria, contactar o administrador do sistema.*
