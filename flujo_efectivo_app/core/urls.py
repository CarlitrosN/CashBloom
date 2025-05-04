# core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('seleccionar-empresa/<int:empresa_id>/', views.seleccionar_empresa_activa, name='seleccionar_empresa'),
    path('seleccionar-empresa/', views.selector_empresa_view, name='selector_empresa'),
    # Otras URLs de core si las tienes
]