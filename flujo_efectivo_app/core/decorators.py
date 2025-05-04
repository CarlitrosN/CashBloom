
import logging
from functools import wraps

from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.urls import reverse_lazy

from .models import SuscripcionEmpresa

logger = logging.getLogger(__name__)


def plan_feature_required(feature_flag):
    """
    Decorador para vistas de función.
    Verifica si el plan de la empresa activa tiene habilitada
    una característica específica (campo booleano en Plan).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            empresa_id = request.session.get('empresa_activa_id')
            if not empresa_id:
                messages.error(request, "Seleccione una empresa primero.")
                return redirect('gestion:dashboard')

            try:
                suscripcion = (
                    SuscripcionEmpresa.objects
                    .select_related('plan')
                    .get(empresa_id=empresa_id)
                )
            except SuscripcionEmpresa.DoesNotExist:
                messages.error(
                    request,
                    "Su empresa no tiene un plan de suscripción asignado. "
                    "Contacte al administrador."
                )
                return redirect('gestion:dashboard')

            # Verificar validez y flag
            try:
                if suscripcion.is_valid() and getattr(suscripcion.plan, feature_flag):
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(
                        request,
                        f"Su plan actual ('{suscripcion.plan.nombre}') no incluye "
                        "acceso a esta funcionalidad. Considere actualizar su plan."
                    )
                    return redirect('gestion:dashboard')
            except AttributeError:
                logger.error(
                    f"plan_feature_required: Flag '{feature_flag}' "
                    "no existe en modelo Plan."
                )
                messages.error(
                    request,
                    "Configuración incorrecta de la funcionalidad. "
                    "Contacte al administrador."
                )
                return redirect('gestion:dashboard')

        return _wrapped_view
    return decorator