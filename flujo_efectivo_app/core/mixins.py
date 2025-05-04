import logging

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.urls import reverse_lazy

from .models import SuscripcionEmpresa

logger = logging.getLogger(__name__)


class PlanFeatureRequiredMixin(AccessMixin):
    """
    Mixin para CBVs. Verifica característica del plan de la empresa activa.
    La clase hija DEBE definir 'feature_flag' (ej: 'permite_aging_report').
    """
    feature_flag = None
    permission_denied_message = "Su plan actual no incluye acceso a esta funcionalidad."
    redirect_url_on_fail = reverse_lazy('gestion:dashboard')

    def dispatch(self, request, *args, **kwargs):
        if not self.feature_flag:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} debe definir 'feature_flag'."
            )

        empresa_id = request.session.get('empresa_activa_id')
        if not empresa_id:
            messages.error(request, "Seleccione una empresa primero.")
            return redirect(self.redirect_url_on_fail)

        try:
            suscripcion = (
                SuscripcionEmpresa.objects
                .select_related('plan')
                .get(empresa_id=empresa_id)
            )
        except SuscripcionEmpresa.DoesNotExist:
            messages.error(
                request,
                "Su empresa no tiene un plan de suscripción asignado."
            )
            return redirect(self.redirect_url_on_fail)

        try:
            tiene_permiso = (
                suscripcion.is_valid() and
                getattr(suscripcion.plan, self.feature_flag)
            )
        except AttributeError:
            logger.error(
                f"PlanFeatureRequiredMixin: Flag '{self.feature_flag}' "
                "no existe en modelo Plan."
            )
            messages.error(
                request,
                "Configuración incorrecta de la funcionalidad. Contacte al administrador."
            )
            return redirect(self.redirect_url_on_fail)

        if not tiene_permiso:
            messages.error(
                request,
                f"Su plan actual ('{suscripcion.plan.nombre}') no incluye "
                "acceso a esta funcionalidad. Considere actualizar su plan."
            )
            return redirect(self.redirect_url_on_fail)

        return super().dispatch(request, *args, **kwargs)