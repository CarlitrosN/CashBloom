# config_proyecto/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings           # <--- Importar settings
from django.conf.urls.static import static # <--- Importar static
# Importar vistas de autenticación
from django.contrib.auth import views as auth_views
# Importar la vista del dashboard para la raíz (si aún no está)
from gestion.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('gestion/', include('gestion.urls')), # URLs de tu app principal

    # --- URLs de Autenticación ---
    # Usaremos las vistas incorporadas de Django, pero con nuestras plantillas
    path('cuentas/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html' # Especifica nuestra plantilla personalizada
        ), name='login'),
    path('cuentas/logout/', auth_views.LogoutView.as_view(
        # next_page=reverse_lazy('login') # Redirigir a login después de logout
        ), name='logout'),
    # Añadir otras URLs de auth si las necesitas (cambio de pass, etc.)
    path('cuentas/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('cuentas/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('cuentas/password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    # ... etc ...

    path('empresas/', include('core.urls')),

    # --- Ruta Raíz ---
    # Redirigir la raíz del sitio al dashboard si está autenticado, o al login si no
    # O simplemente mostrar siempre el dashboard (protegido por @login_required)
    # O mostrar una página de bienvenida simple.
    # Por ahora, apuntemos al dashboard de gestion.
    # Asegúrate que 'gestion:dashboard' exista en gestion/urls.py
    path('', dashboard_view, name='home'), # O redirigir: from django.views.generic import RedirectView; path('', RedirectView.as_view(pattern_name='gestion:dashboard', permanent=False))

]

# Añadir esto al final del archivo para servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)