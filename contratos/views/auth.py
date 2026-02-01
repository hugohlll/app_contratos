from django.contrib.auth import logout
from django.shortcuts import redirect

def sair(request):
    logout(request)
    return redirect('pesquisa')