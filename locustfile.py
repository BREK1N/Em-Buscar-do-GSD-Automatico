"""
Load test — Portal GSD
Uso: locust -f locustfile.py --host=http://localhost:8080
     locust -f locustfile.py --host=http://localhost:8080 --users=50 --spawn-rate=5 --run-time=3m --headless
"""
import os, re, random, logging, itertools, threading
from locust import HttpUser, task, between, events
from locust.exception import StopUser

logger = logging.getLogger("locust.gsd")

# Pool de usuários de teste — cada instância pega um diferente
# Garante que não haja colisão de rate-limit por usuário
_TEST_USERS = [(f"loadtest_user{i:02d}", "LoadTest@2024!") for i in range(1, 21)]
_user_cycle  = itertools.cycle(_TEST_USERS)
_cycle_lock  = threading.Lock()


def _next_credentials():
    with _cycle_lock:
        return next(_user_cycle)


# ---------------------------------------------------------------------------
# Login helper
# ---------------------------------------------------------------------------

def _login(client, username: str, password: str) -> bool:
    client.get("/login/", name="/login/[GET]")
    token = client.cookies.get("csrftoken", "")
    resp = client.post(
        "/login/",
        data={"username": username, "password": password, "csrfmiddlewaretoken": token},
        headers={"Referer": f"{client.base_url}/login/"},
        name="/login/[POST]",
        allow_redirects=True,
    )
    ok = resp.ok and "login" not in resp.url.lower()
    if not ok:
        logger.warning("Login falhou (%s) — status %s | url %s", username, resp.status_code, resp.url)
    return ok


def _extract_ids(html: str, pattern: str) -> list:
    return list(set(re.findall(pattern, html)))[:10]


# ---------------------------------------------------------------------------
# Usuário principal — cobre todos os módulos críticos
# ---------------------------------------------------------------------------

class UsuarioGSD(HttpUser):
    wait_time = between(1, 4)
    _patd_ids: list = []
    _missao_ids: list = []
    _efetivo_ids: list = []

    def on_start(self):
        username, password = _next_credentials()
        if not _login(self.client, username, password):
            raise StopUser()
        self._seed_ids()

    def _seed_ids(self):
        """Descobre IDs reais para usar nos testes de detalhe (1 request cada)."""
        r = self.client.get("/Ouvidoria/patd/", name="[seed] patd list")
        if r.ok:
            self._patd_ids = _extract_ids(r.text, r'/Ouvidoria/patd/(\d+)/')

        r = self.client.get("/secao_operacoes/missoes/", name="[seed] missoes list")
        if r.ok:
            self._missao_ids = _extract_ids(r.text, r'/secao_operacoes/missoes/(\d+)/')

        r = self.client.get("/secao_pessoal/efetivo/", name="[seed] efetivo list")
        if r.ok:
            self._efetivo_ids = _extract_ids(r.text, r'/secao_pessoal/efetivo/(\d+)/')

    # --- Home (peso 15) ---

    @task(5)
    def home_dashboard(self):
        self.client.get("/home/", name="home/dashboard")

    @task(5)
    def inbox(self):
        self.client.get("/comunicacoes/", name="caixa_entrada/inbox")

    @task(3)
    def notificacoes(self):
        self.client.get("/notificacoes/api/", name="notificacoes/api")

    @task(2)
    def inbox_check(self):
        self.client.get("/comunicacoes/api/check/", name="comunicacoes/api/check")

    # --- Ouvidoria (peso 35) ---

    @task(8)
    def ouvidoria_lista_patd(self):
        self.client.get("/Ouvidoria/patd/", name="Ouvidoria/patd/lista")

    @task(6)
    def ouvidoria_detalhe_patd(self):
        if not self._patd_ids:
            return
        pk = random.choice(self._patd_ids)
        self.client.get(f"/Ouvidoria/patd/{pk}/", name="Ouvidoria/patd/<id>")

    @task(5)
    def ouvidoria_dashboard(self):
        self.client.get("/Ouvidoria/", name="Ouvidoria/dashboard")

    @task(4)
    def ouvidoria_relatorio_json(self):
        self.client.get("/Ouvidoria/relatorio/dados.json", name="Ouvidoria/relatorio.json")

    @task(4)
    def ouvidoria_dashboard_cmdt(self):
        self.client.get("/Ouvidoria/comandante/dashboard/", name="Ouvidoria/cmdt-dashboard")

    @task(4)
    def ouvidoria_atribuicoes(self):
        self.client.get("/Ouvidoria/minhas-atribuicoes/", name="Ouvidoria/atribuicoes")

    @task(4)
    def ouvidoria_patds_expirados(self):
        self.client.get("/Ouvidoria/notificacoes/patds-expirados/", name="Ouvidoria/patds-expirados")

    # --- Operações (peso 20) ---

    @task(5)
    def operacoes_missoes(self):
        self.client.get("/secao_operacoes/missoes/", name="Operacoes/missoes")

    @task(5)
    def operacoes_painel(self):
        self.client.get("/secao_operacoes/missoes/painel/", name="Operacoes/painel")

    @task(5)
    def operacoes_escalas(self):
        self.client.get("/secao_operacoes/escalas/", name="Operacoes/escalas")

    @task(3)
    def operacoes_detalhe_missao(self):
        if not self._missao_ids:
            return
        pk = random.choice(self._missao_ids)
        self.client.get(f"/secao_operacoes/missoes/{pk}/", name="Operacoes/missao/<id>")

    @task(2)
    def operacoes_busca(self):
        self.client.get(
            "/secao_operacoes/missoes/api/busca/?q=missao",
            name="Operacoes/api/busca",
        )

    # --- Pessoal (peso 15) ---

    @task(5)
    def pessoal_efetivo(self):
        self.client.get("/secao_pessoal/efetivo/", name="Pessoal/efetivo")

    @task(4)
    def pessoal_painel_chefe(self):
        self.client.get("/secao_pessoal/painel-chefe/", name="Pessoal/painel-chefe")

    @task(3)
    def pessoal_indisponiveis(self):
        self.client.get("/secao_pessoal/controle/indisponiveis/", name="Pessoal/indisponiveis")

    @task(3)
    def pessoal_busca(self):
        self.client.get(
            "/secao_pessoal/api/search-militares/?q=silva",
            name="Pessoal/api/search",
        )

    # --- Informática (peso 10) — requer grupo, 403 esperado p/ usuários básicos ---

    @task(4)
    def informatica_dashboard(self):
        with self.client.get("/informatica/", name="Informatica/dashboard", catch_response=True) as r:
            if r.status_code == 403:
                r.success()

    @task(3)
    def informatica_monitoramento(self):
        with self.client.get("/informatica/monitoramento/", name="Informatica/monitoramento", catch_response=True) as r:
            if r.status_code == 403:
                r.success()

    @task(3)
    def informatica_logs(self):
        with self.client.get("/informatica/api/logs/", name="Informatica/api/logs", catch_response=True) as r:
            if r.status_code == 403:
                r.success()

    # --- ESI (peso 5) — requer grupo ESI, 403 esperado p/ usuários básicos ---

    @task(3)
    def esi_dashboard(self):
        with self.client.get("/esi/", name="ESI/dashboard", catch_response=True) as r:
            if r.status_code == 403:
                r.success()

    @task(2)
    def esi_missoes(self):
        with self.client.get("/esi/missoes/", name="ESI/missoes", catch_response=True) as r:
            if r.status_code == 403:
                r.success()


# ---------------------------------------------------------------------------
# Relatório final no terminal
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def _resumo(environment, **kwargs):
    s = environment.stats.total
    if s.num_requests == 0:
        return
    print("\n" + "=" * 60)
    print("LOAD TEST — Portal GSD")
    print("=" * 60)
    print(f"  Requests    : {s.num_requests}")
    print(f"  Falhas      : {s.num_failures} ({s.fail_ratio * 100:.1f}%)")
    print(f"  RPS médio   : {total_rps(environment):.1f}")
    print(f"  P50         : {s.get_response_time_percentile(0.50):.0f} ms")
    print(f"  P90         : {s.get_response_time_percentile(0.90):.0f} ms")
    print(f"  P99         : {s.get_response_time_percentile(0.99):.0f} ms")
    print(f"  Pior        : {s.max_response_time:.0f} ms")
    print("=" * 60)


def total_rps(env):
    try:
        return env.stats.total.total_rps
    except Exception:
        return 0.0
