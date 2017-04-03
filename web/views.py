from django.shortcuts import render
from .models import Panel

def index(request):
    panels = Panel.objects.all()
    return render(request, 'web/index.html', {'panels': panels})