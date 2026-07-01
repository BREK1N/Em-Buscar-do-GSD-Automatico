"""
Cria 50 PATDs de teste para o GSD e 50 para o BINFAE.

Uso:
    python manage.py seed_patds
    python manage.py seed_patds --limpar   # apaga os de teste antes de recriar
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from Ouvidoria.models import PATD
from Ouvidoria.views.helpers import get_next_patd_number
from Secao_pessoal.models import Efetivo


TRANSGRESSOES = [
    "ausentou-se do quartel sem autorização do superior hierárquico",
    "chegou atrasado ao local de instrução sem apresentar justo motivo",
    "foi flagrado em estado de embriaguez durante o expediente de serviço",
    "desacatou superior hierárquico em público perante outros militares",
    "faltou ao serviço sem apresentar justificativa no prazo regulamentar",
    "deixou de cumprir ordem do superior sem justificativa plausível",
    "foi encontrado dormindo durante o serviço de guarda noturna",
    "utilizou equipamento da organização para fins particulares sem autorização",
    "apresentou-se ao serviço com uniforme em desacordo com as normas vigentes",
    "recusou-se a cumprir escala de serviço determinada pelo superior",
    "travam disputa e rixa corporal com colega militar nas dependências da OM",
    "ausentou-se do local de serviço sem comunicar ao encarregado de turno",
    "praticou jogo proibido nas dependências da organização militar",
    "proferiu palavras ofensivas ao superior hierárquico durante instrução",
    "danificou equipamento da OM por negligência no manuseio",
    "não compareceu à formatura matinal sem justificativa aceita",
    "foi flagrado com uso de aparelho celular durante serviço de guarda",
    "ausentou-se de missão antes do término sem autorização",
    "cometeu ato obsceno nas dependências da organização militar",
    "faltou ao serviço em data de escala sem comunicação prévia ao superior",
]

ITENS_RDAER = [
    [{"numero": 17, "descricao": "ausentar-se sem licença do local do serviço ou do lugar em que deve permanecer"}],
    [{"numero": 18, "descricao": "faltar ou chegar atrasado, sem justo motivo, ao local onde deva comparecer"}],
    [{"numero": 58, "descricao": "embriagar-se com bebida alcoólica"}],
    [{"numero": 24, "descricao": "desrespeitar superior"}],
    [{"numero": 57, "descricao": "travar disputa, rixa ou luta corporal"}],
    [{"numero": 17, "descricao": "ausentar-se sem licença do local do serviço"}, {"numero": 18, "descricao": "faltar ao local onde deva comparecer"}],
    [{"numero": 100, "descricao": "concorrer de qualquer modo para a prática de transgressão"}],
    [{"numero": 53, "descricao": "praticar jogo proibido"}],
    [{"numero": 32, "descricao": "proferir palavras ou praticar atos ofensivos à moral e aos bons costumes"}],
]

PUNICOES = [
    ("Dois (02)", "detenção"),
    ("Quatro (04)", "detenção"),
    ("Seis (06)", "detenção"),
    ("Oito (08)", "detenção"),
    ("Dez (10)", "detenção"),
    ("Dois (02)", "prisão"),
    ("Quatro (04)", "prisão"),
    ("Repreensão verbal", "repreensão"),
    ("Repreensão por escrito", "repreensão"),
]

STATUSES_DISTRIBUICAO = [
    ("confeccao_fr_ficha", 8),
    ("ciencia_militar", 6),
    ("aguardando_justificativa", 5),
    ("em_apuracao", 8),
    ("aguardando_punicao", 5),
    ("analise_comandante", 4),
    ("aguardando_assinatura_npd", 3),
    ("finalizado", 10),
    ("definicao_oficial", 1),
]

CIRCUNSTANCIAS_EXEMPLOS = [
    {"atenuantes": ["a"], "agravantes": []},
    {"atenuantes": ["a"], "agravantes": ["i"]},
    {"atenuantes": ["a"], "agravantes": ["b", "i"]},
    {"atenuantes": [], "agravantes": ["a", "i"]},
    {"atenuantes": ["a", "c"], "agravantes": []},
    {"atenuantes": ["a"], "agravantes": ["c"]},
]


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _build_pool() -> list:
    """Expande STATUSES_DISTRIBUICAO numa lista plana para escolha aleatória."""
    pool = []
    for status, qty in STATUSES_DISTRIBUICAO:
        pool.extend([status] * qty)
    return pool


def _criar_lote(qtd: int, org: str, data_start: date, data_end: date, efetivos: list, stdout):
    pool_status = _build_pool()
    criados = 0

    for i in range(qtd):
        data_ocorrencia = _random_date(data_start, data_end)
        data_inicio = timezone.make_aware(
            timezone.datetime(data_ocorrencia.year, data_ocorrencia.month, data_ocorrencia.day,
                              random.randint(7, 17), random.randint(0, 59))
        )

        militar = random.choice(efetivos) if efetivos else None
        transgressao = random.choice(TRANSGRESSOES)
        status = random.choice(pool_status)
        itens = random.choice(ITENS_RDAER)
        circ = random.choice(CIRCUNSTANCIAS_EXEMPLOS)
        dias_pun, tipo_pun = random.choice(PUNICOES)

        numero = get_next_patd_number(data_inicio)

        oficio = f"OF {random.randint(1, 200):03d}/{data_ocorrencia.year}"

        patd = PATD(
            militar=militar,
            transgressao=transgressao,
            numero_patd=numero,
            data_inicio=data_inicio,
            data_ocorrencia=data_ocorrencia,
            status=status,
            oficio_transgressao=oficio,
            protocolo_comaer=f"COMAER-{random.randint(10000, 99999)}" if random.random() > 0.4 else "",
            itens_enquadrados=itens,
            circunstancias=circ,
            dias_punicao=dias_pun if status == "finalizado" else None,
            punicao=tipo_pun if status == "finalizado" else None,
            punicao_sugerida=f"{dias_pun} de {tipo_pun}",
            comportamento='Permanece no "Bom comportamento"',
            # Marca como teste para facilitar limpeza
            comprovante="[PATD DE TESTE — seed_patds]",
        )
        patd.save()  # save() define organizacao e snapshots automaticamente
        criados += 1
        stdout.write(f"  [{org}] #{numero}/{data_inicio.year} — {status} — {militar or 'sem militar'}")

    return criados


class Command(BaseCommand):
    help = "Cria 50 PATDs de teste para GSD e 50 para BINFAE"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove PATDs de teste existentes antes de criar novos",
        )
        parser.add_argument(
            "--qtd",
            type=int,
            default=50,
            help="Quantidade de PATDs por organização (padrão: 50)",
        )
        parser.add_argument(
            "--so-gsd",
            action="store_true",
            help="Cria apenas PATDs GSD, sem criar BINFAE",
        )
        parser.add_argument(
            "--so-binfae",
            action="store_true",
            help="Cria apenas PATDs BINFAE, sem criar GSD",
        )
        parser.add_argument(
            "--gsd-start",
            type=str,
            default=None,
            help="Data início para lote GSD (AAAA-MM-DD). Padrão: 2024-01-01",
        )
        parser.add_argument(
            "--gsd-end",
            type=str,
            default=None,
            help="Data fim para lote GSD (AAAA-MM-DD). Padrão: 2026-05-31",
        )

    def handle(self, *args, **options):
        qtd = options["qtd"]

        if options["limpar"]:
            apagados, _ = PATD.all_objects.filter(
                comprovante="[PATD DE TESTE — seed_patds]"
            ).delete()
            self.stdout.write(self.style.WARNING(f"Removidos {apagados} PATDs de teste."))

        efetivos = list(Efetivo.objects.all()[:100])
        if not efetivos:
            self.stdout.write(self.style.WARNING("Nenhum Efetivo no banco — PATDs criadas sem militar vinculado."))

        gsd_start = date.fromisoformat(options["gsd_start"]) if options["gsd_start"] else date(2024, 1, 1)
        gsd_end   = date.fromisoformat(options["gsd_end"])   if options["gsd_end"]   else date(2026, 5, 31)

        n_gsd = 0
        if not options["so_binfae"]:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nCriando {qtd} PATDs — GSD ({gsd_start} → {gsd_end})"))
            n_gsd = _criar_lote(
                qtd=qtd,
                org="GSD",
                data_start=gsd_start,
                data_end=gsd_end,
                efetivos=efetivos,
                stdout=self.stdout,
            )

        n_binfae = 0
        if not options["so_gsd"]:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nCriando {qtd} PATDs — BINFAE"))
            n_binfae = _criar_lote(
                qtd=qtd,
                org="BINFAE",
                data_start=date(2026, 6, 1),
                data_end=date(2026, 6, 30),
                efetivos=efetivos,
                stdout=self.stdout,
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nConcluído: {n_gsd} PATDs GSD + {n_binfae} PATDs BINFAE criadas."
        ))
