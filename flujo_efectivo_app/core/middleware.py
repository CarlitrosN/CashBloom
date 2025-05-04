# core/middleware.py (o gestion/middleware.py)
from django.shortcuts import redirect
from django.urls import reverse

# Lista de nombres de URL que NO requieren una empresa activa
# (ej: login, logout, selector de empresa, admin, etc.)
URLS_SIN_EMPRESA = [
    'login', 'logout', 'admin:index', 'admin:login', 'admin:logout',
    'selector_empresa', 'seleccionar_empresa',
    # Añade aquí cualquier otra URL pública o que no dependa de la empresa
]

class SeleccionEmpresaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # No aplicar el middleware para rutas del admin u otras excluidas
        resolver_match = request.resolver_match
        if not resolver_match or resolver_match.namespace == 'admin' or resolver_match.url_name in URLS_SIN_EMPRESA:
            return self.get_response(request)

        # Verificar si el usuario está autenticado
        if not request.user.is_authenticated:
             # Si no está autenticado, las vistas protegidas lo redirigirán al login
             return self.get_response(request)

        # Verificar si hay una empresa activa en la sesión Y si el usuario pertenece a ella
        empresa_activa_id = request.session.get('empresa_activa_id')

        if not empresa_activa_id:
            # Si no hay empresa en sesión, redirigir al selector
            # (excepto si está yendo al propio selector)
            return redirect(reverse('core:selector_empresa')) # Asegúrate que el nombre sea correcto
        else:
            # Opcional: Verificar si el usuario realmente pertenece a la empresa en sesión
            # Esto evita que alguien manipule la sesión.
            if not request.user.empresas_asignadas.filter(empresa_id=empresa_activa_id).exists():
                # Si no pertenece, borrar la sesión y redirigir al selector
                del request.session['empresa_activa_id']
                if 'empresa_activa_nombre' in request.session: del request.session['empresa_activa_nombre']
                if 'empresa_activa_moneda' in request.session: del request.session['empresa_activa_moneda']
                messages.warning(request, "La empresa seleccionada ya no es válida para tu usuario.")
                return redirect(reverse('core:selector_empresa'))

        # Si todo está bien, continuar con la vista normal
        response = self.get_response(request)
        return response