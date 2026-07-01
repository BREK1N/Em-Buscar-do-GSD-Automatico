from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verifica PATDs travadas em aguardando_assinatura_npd e avança as que já têm todas as assinaturas.'

    def handle(self, *args, **options):
        from Ouvidoria.models import PATD
        from Ouvidoria.views.commander import _check_and_finalize_patd

        pendentes = PATD.objects.filter(status='aguardando_assinatura_npd')
        total = pendentes.count()
        avancadas = 0
        bloqueadas = []

        self.stdout.write(f'Verificando {total} PATD(s) em aguardando_assinatura_npd...')

        for patd in pendentes:
            if _check_and_finalize_patd(patd):
                avancadas += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ PATD Nº {patd.numero_patd} avançada para periodo_reconsideracao'
                ))
            else:
                from Ouvidoria.views.helpers import get_document_pages
                pages = get_document_pages(patd)
                raw = ''.join(pages)
                required = raw.count('{Assinatura Militar Arrolado}')
                provided = sum(1 for s in (patd.assinaturas_militar or []) if s)
                motivo = []
                if provided < required:
                    motivo.append(f'assinatura militar: {provided}/{required}')
                if patd.testemunha1 and not patd.assinatura_testemunha1:
                    motivo.append('testemunha 1 sem assinatura')
                if patd.testemunha2 and not patd.assinatura_testemunha2:
                    motivo.append('testemunha 2 sem assinatura')
                bloqueadas.append((patd.numero_patd, motivo))
                self.stdout.write(self.style.WARNING(
                    f'  ✗ PATD Nº {patd.numero_patd} bloqueada: {", ".join(motivo) or "motivo desconhecido"}'
                ))

        self.stdout.write('')
        self.stdout.write(f'Resultado: {avancadas} avançada(s), {len(bloqueadas)} ainda bloqueada(s).')
