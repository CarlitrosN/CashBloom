# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import Empresa, UsuarioEmpresa

@login_required
def seleccionar_empresa_activa(request, empresa_id):
    """
    Establece la empresa activa en la sesión del usuario.
    Verifica que el usuario tenga permiso para esa empresa.
    """
    # Buscar la asignación específica del usuario a la empresa solicitada
    asignacion = get_object_or_404(
        UsuarioEmpresa,
        usuario=request.user,
        empresa_id=empresa_id
    )

    # Si se encontró la asignación (el get_object_or_404 ya lo valida),
    # guardar el ID y el nombre en la sesión.
    request.session['empresa_activa_id'] = asignacion.empresa.id
    request.session['empresa_activa_nombre'] = asignacion.empresa.razon_social
    request.session['empresa_activa_moneda'] = asignacion.empresa.moneda # Guardar moneda

    messages.success(request, f"Empresa activa cambiada a: {asignacion.empresa.razon_social}")

    # Redirigir al Dashboard (o a la página desde donde vino si se implementa 'next')
    return redirect('gestion:dashboard')

# Opcional: Vista para mostrar el selector si no hay empresa activa
@login_required
def selector_empresa_view(request):
    """Muestra la página para seleccionar una empresa si no hay una activa."""
    empresas_usuario = UsuarioEmpresa.objects.filter(usuario=request.user).select_related('empresa').order_by('empresa__razon_social')

    if not empresas_usuario.exists():
        messages.error(request, "No tienes ninguna empresa asignada. Contacta al administrador.")
        # TODO: Redirigir a una página de error o logout?
        return redirect('logout') # O a una página específica

    # Si solo tiene una empresa, seleccionarla automáticamente y redirigir
    if empresas_usuario.count() == 1:
        empresa_unica = empresas_usuario.first().empresa
        request.session['empresa_activa_id'] = empresa_unica.id
        request.session['empresa_activa_nombre'] = empresa_unica.razon_social
        request.session['empresa_activa_moneda'] = empresa_unica.moneda
        messages.info(request, f"Empresa activa establecida: {empresa_unica.razon_social}")
        return redirect('gestion:dashboard')

    # Si tiene varias, mostrar selector
    context = {
        'titulo_pagina': "Seleccionar Empresa",
        'empresas_usuario': empresas_usuario
    }
    return render(request, 'core/selector_empresa.html', context) # Nueva plantilla
