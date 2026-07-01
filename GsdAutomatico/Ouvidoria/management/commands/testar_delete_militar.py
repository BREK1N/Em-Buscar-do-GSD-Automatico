"""
Testa o comportamento da PATD quando o militar vinculado é excluído.

Etapas:
  1. Cria um Efetivo de teste
  2. Cria uma PATD para esse Efetivo (com snapshots preenchidos)
  3. Soft delete do Efetivo (deleted=True) — simula a exclusão pela UI
  4. Verifica que a PATD ainda existe e os dados estão corretos
  5. Hard delete real (remove do banco) — dispara SET_NULL no FK
  6. Verifica que a PATD ainda existe, militar=None, mas snapshots preservados
  7. Limpa tudo (remove PATD e Efetivo criados pelo teste)

Uso:
    python manage.py testar_delete_militar
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection

from Secao_pessoal.models import Efetivo
from Ouvidoria.models import PATD


NOME_TESTE = "TESTE-DELETE-MILITAR"
SARAM_TESTE = 9999999


class Command(BaseCommand):
    help = "Verifica que apagar um Efetivo não apaga a PATD vinculada"

    def handle(self, *args, **options):
        ok = self.style.SUCCESS
        err = self.style.ERROR
        info = self.style.WARNING

        self._limpar_residuos()

        # ── 1. Criar Efetivo de teste ──────────────────────────────────────
        self.stdout.write("\n[1/6] Criando Efetivo de teste...")
        efetivo = Efetivo(
            posto="CB",
            nome_guerra=NOME_TESTE,
            nome_completo="Cabo Teste Delete Militar",
            saram=SARAM_TESTE,
        )
        efetivo.save()
        self.stdout.write(ok(f"     Efetivo criado: pk={efetivo.pk} | {efetivo}"))

        # ── 2. Criar PATD vinculada ────────────────────────────────────────
        self.stdout.write("\n[2/6] Criando PATD de teste para esse militar...")
        data_inicio = timezone.make_aware(timezone.datetime(2025, 3, 15, 9, 0))
        patd = PATD(
            militar=efetivo,
            transgressao="[TESTE] transgressão gerada pelo testar_delete_militar",
            data_inicio=data_inicio,
            data_ocorrencia=data_inicio.date(),
            status="confeccao_fr_ficha",
            comprovante="[TESTE — testar_delete_militar]",
        )
        patd.save()  # save() preenche snapshots e organizacao automaticamente
        patd_pk = patd.pk
        self.stdout.write(ok(f"     PATD criada: pk={patd_pk} | N°{patd.numero_patd}"))
        self.stdout.write(info(f"     snapshot nome_guerra : {patd.militar_nome_guerra_snapshot}"))
        self.stdout.write(info(f"     snapshot posto        : {patd.militar_posto_snapshot}"))
        self.stdout.write(info(f"     snapshot nome_completo: {patd.militar_nome_completo_snapshot}"))
        self.stdout.write(info(f"     snapshot saram        : {patd.militar_saram_snapshot}"))

        # ── 3. Soft delete do Efetivo ──────────────────────────────────────
        self.stdout.write("\n[3/6] Soft delete do Efetivo (simula exclusão pela UI)...")
        efetivo.deleted = True
        efetivo.deleted_at = timezone.now()
        efetivo.save(update_fields=["deleted", "deleted_at"])
        self.stdout.write(ok(f"     Efetivo marcado como deleted=True"))

        # ── 4. Verificar PATD após soft delete ────────────────────────────
        self.stdout.write("\n[4/6] Verificando PATD após soft delete...")
        patd.refresh_from_db()
        assert patd.pk == patd_pk, "PATD sumiu após soft delete!"
        assert patd.militar_id == efetivo.pk, "FK militar foi zerada no soft delete!"
        self.stdout.write(ok(f"     PATD ainda existe: pk={patd.pk}"))
        self.stdout.write(ok(f"     FK militar ainda válida: militar_id={patd.militar_id}"))
        self.stdout.write(ok(f"     str(patd): {patd}"))

        # ── 5. Hard delete real do Efetivo (dispara SET_NULL) ─────────────
        self.stdout.write("\n[5/6] Hard delete real do Efetivo (remove do banco)...")
        efetivo_pk = efetivo.pk
        Efetivo.all_objects.filter(pk=efetivo_pk).delete()
        self.stdout.write(ok(f"     Efetivo pk={efetivo_pk} removido do banco"))

        # ── 6. Verificar PATD após hard delete ────────────────────────────
        self.stdout.write("\n[6/6] Verificando PATD após hard delete...")
        patd.refresh_from_db()
        assert patd.pk == patd_pk, "PATD sumiu após hard delete!"
        assert patd.militar_id is None, f"FK militar deveria ser NULL, mas é {patd.militar_id}"
        assert patd.militar_nome_guerra_snapshot == NOME_TESTE, "Snapshot nome_guerra perdido!"
        assert patd.militar_posto_snapshot == "CB", "Snapshot posto perdido!"
        assert patd.militar_saram_snapshot == SARAM_TESTE, "Snapshot saram perdido!"
        self.stdout.write(ok(f"     PATD ainda existe: pk={patd.pk}"))
        self.stdout.write(ok(f"     FK militar=None (SET_NULL funcionou corretamente)"))
        self.stdout.write(ok(f"     Snapshot nome_guerra : {patd.militar_nome_guerra_snapshot}"))
        self.stdout.write(ok(f"     Snapshot posto        : {patd.militar_posto_snapshot}"))
        self.stdout.write(ok(f"     Snapshot saram        : {patd.militar_saram_snapshot}"))
        self.stdout.write(ok(f"     str(patd): {patd}"))

        # ── Limpeza ────────────────────────────────────────────────────────
        self.stdout.write("\nLimpando dados de teste...")
        PATD.all_objects.filter(pk=patd_pk).delete()
        self.stdout.write(ok("     PATD de teste removida."))

        self.stdout.write(self.style.SUCCESS(
            "\n✓ Teste concluído com sucesso. "
            "A PATD sobrevive à exclusão do militar e mantém os snapshots.\n"
        ))

    def _limpar_residuos(self):
        """Remove resíduos de execuções anteriores do comando."""
        n_patd = PATD.all_objects.filter(comprovante="[TESTE — testar_delete_militar]").delete()[0]
        n_ef   = Efetivo.all_objects.filter(saram=SARAM_TESTE).delete()[0]
        if n_patd or n_ef:
            self.stdout.write(self.style.WARNING(
                f"Removidos resíduos de execução anterior: {n_patd} PATD(s), {n_ef} Efetivo(s)."
            ))
