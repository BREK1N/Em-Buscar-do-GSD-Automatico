from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from datetime import date
from .models import Escala, TurnoEscala
from .forms import EscalaForm, TurnoEscalaForm
from Secao_pessoal.models import Efetivo, Notificacao

@login_required
def index(request):
    return render(request, 'Secao_operacoes/base.html')

@login_required
def escala_list(request):
    from django.db.models import Q
    search_query = request.GET.get('q', '')
    hoje = date.today()
    
    escalas = Escala.objects.all().order_by('nome')
    
    resultados_pesquisa = []
    if search_query:
        turnos = TurnoEscala.objects.filter(
            Q(militar__nome_guerra__icontains=search_query) | 
            Q(escala__nome__icontains=search_query)
        ).select_related('escala', 'militar').order_by('data')
        resultados_pesquisa = turnos
        
    for escala in escalas:
        escala.turnos_hoje = escala.turnos.filter(data=hoje)
        
    return render(request, 'Secao_operacoes/escala_list.html', {
        'escalas': escalas,
        'resultados_pesquisa': resultados_pesquisa,
        'search_query': search_query,
        'hoje': hoje
    })

@login_required
def escala_create(request):
    if request.method == 'POST':
        form = EscalaForm(request.POST)
        if form.is_valid():
            escala = form.save()
            messages.success(request, 'Escala criada com sucesso!')
            return redirect('Secao_operacoes:escala_detail', pk=escala.pk)
    else:
        form = EscalaForm()
    return render(request, 'Secao_operacoes/escala_form.html', {'form': form, 'title': 'Nova Escala'})

@login_required
def escala_edit(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        form = EscalaForm(request.POST, instance=escala)
        if form.is_valid():
            form.save()
            messages.success(request, 'Escala atualizada com sucesso!')
            return redirect('Secao_operacoes:escala_detail', pk=escala.pk)
    else:
        form = EscalaForm(instance=escala)
    return render(request, 'Secao_operacoes/escala_form.html', {'form': form, 'title': 'Editar Escala', 'escala': escala})

@login_required
def escala_detail(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        form = TurnoEscalaForm(request.POST, escala_id=escala.pk)
        if form.is_valid():
            turno = form.save(commit=False)
            turno.escala = escala
            turno.save()
            
            # Enviar notificação para o militar escalado
            militar_logado = None
            if hasattr(request.user, 'profile') and request.user.profile.militar:
                militar_logado = request.user.profile.militar
            
            # Se não tiver um perfil de militar (ex: superuser), usamos o próprio destinatário ou None.
            # No entanto, remetente é obrigatório. Se não tiver militar_logado, vamos pegar o primeiro oficial ou superuser militar.
            if not militar_logado:
                militar_logado = Efetivo.objects.filter(oficial=True).first()
            
            if militar_logado and turno.militar:
                Notificacao.objects.create(
                    remetente=militar_logado,
                    destinatario=turno.militar,
                    titulo=f"Escala de Serviço - {escala.nome}",
                    mensagem=f"Você foi escalado para o serviço de {escala.nome} no dia {turno.data.strftime('%d/%m/%Y')}. Escalado por: {militar_logado.nome_guerra}."
                )

            messages.success(request, f'Militar {turno.militar.nome_guerra} escalado para {turno.data}!')
            return redirect('Secao_operacoes:escala_detail', pk=escala.pk)
    else:
        form = TurnoEscalaForm(escala_id=escala.pk)
    
    turnos = escala.turnos.all().order_by('data')
    return render(request, 'Secao_operacoes/escala_detail.html', {
        'escala': escala,
        'form': form,
        'turnos': turnos
    })

@login_required
def turno_delete(request, pk):
    turno = get_object_or_404(TurnoEscala, pk=pk)
    escala_pk = turno.escala.pk
    if request.method == 'POST':
        turno.delete()
        messages.success(request, 'Turno removido com sucesso!')
    return redirect('Secao_operacoes:escala_detail', pk=escala_pk)

@login_required
def turno_delete_all(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        count = escala.turnos.count()
        escala.turnos.all().delete()
        messages.success(request, f'Todos os {count} turnos da escala foram removidos com sucesso!')
    return redirect('Secao_operacoes:escala_detail', pk=escala.pk)

@login_required
def api_escala_eventos(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    turnos = escala.turnos.all()
    eventos = []
    for turno in turnos:
        eventos.append({
            'id': turno.id,
            'title': turno.militar.nome_guerra,
            'start': turno.data.isoformat(),
            'allDay': True,
            'description': turno.observacao or '',
            'color': '#0d6efd', 
        })
    return JsonResponse(eventos, safe=False)
