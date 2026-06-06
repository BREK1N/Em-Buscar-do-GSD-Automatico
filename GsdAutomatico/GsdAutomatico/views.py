from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def task_status_view(request, task_id):
    result = AsyncResult(task_id)
    state = result.state

    if state == 'PENDING':
        return JsonResponse({'status': 'pending'})
    if state == 'STARTED':
        return JsonResponse({'status': 'pending', 'state': 'started'})
    if state == 'SUCCESS':
        return JsonResponse({'status': 'success', 'result': result.result})
    if state == 'FAILURE':
        return JsonResponse({'status': 'error', 'message': str(result.result)}, status=500)
    if state == 'RETRY':
        return JsonResponse({'status': 'pending', 'state': 'retry'})
    return JsonResponse({'status': 'pending', 'state': state})
