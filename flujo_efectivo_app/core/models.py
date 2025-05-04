# core/models.py
from django.db import models
from django.conf import settings # Para usar la configuración del proyecto
from django.utils import timezone
#from django.core.exceptions import ValidationError

# Create your models here.

class Empresa(models.Model):
    identificacion = models.CharField(max_length=50, unique=True, verbose_name="Identificación (NIT, RUT, CUIT, etc.)")
    razon_social = models.CharField(max_length=255, verbose_name="Razón Social")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    pais = models.CharField(max_length=100, verbose_name="País")
    # Moneda: Usaremos el código ISO 4217 (USD, EUR, COP, etc.)
    moneda = models.CharField(
        max_length=3,
        verbose_name="Moneda Principal (ISO 4217)",
        help_text="Ej: USD, EUR, COP, PAB" # Añadir ejemplos
    )
    logo = models.ImageField(upload_to='logos_empresa/', null=True, blank=True, verbose_name="Logotipo")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='empresas_creadas_core', on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Creado por") # Renombrar related_name si es necesario
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='empresas_actualizadas_core', on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    # EL MÉTODO SAVE SINGLETON SE ELIMINA O COMENTA
    # def save(self, *args, **kwargs):
    #     if self.pk or not Empresa.objects.exists():
    #         super().save(*args, **kwargs)
    #     else:
    #         raise ValidationError("Solo puede existir una configuración de Empresa en el sistema.")

    def __str__(self):
        return f"{self.razon_social} ({self.moneda})" # Mostrar moneda en str

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas" # <-- CORREGIDO a Plural
        ordering = ['razon_social']

class UsuarioEmpresa(models.Model):
    """Relación Muchos-a-Muchos entre Usuarios y Empresas."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="empresas_asignadas" # Cómo acceder a las empresas desde el usuario
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="usuarios_asignados" # Cómo acceder a los usuarios desde la empresa
    )
    # --- Opcional: Añadir Roles por Empresa ---
    #class Roles(models.TextChoices):
     #ADMIN = 'ADMIN', 'Administrador'
     #EDITOR = 'EDIT', 'Editor'
     #VIEWER = 'VIEW', 'Visualizador'
     #rol = models.CharField(max_length=6, choices=Roles.choices, default=Roles.VIEWER)
    # ------------------------------------------
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'empresa') # Evitar asignaciones duplicadas
        verbose_name = "Asignación Usuario-Empresa"
        verbose_name_plural = "Asignaciones Usuario-Empresa"
        ordering = ['empresa__razon_social', 'usuario__username']

    def __str__(self):
        # rol_display = f" ({self.get_rol_display()})" if hasattr(self, 'rol') else "" # Si añades rol
        rol_display = ""
        return f"{self.usuario.username} -> {self.empresa.razon_social}{rol_display}"
    
 # ============================================
# ===      MODELOS PLANES Y SUSCRIPCIÓN    ===
# ============================================

class Plan(models.Model):
    """
    Define los diferentes planes de suscripción.
    """
    FREE = 'free'
    PRO = 'pro'
    ENTERPRISE = 'enterprise'

    SLUG_CHOICES = [
        (FREE, 'Gratuito'),
        (PRO, 'Profesional'),
        (ENTERPRISE, 'Empresarial'),
    ]

    slug = models.SlugField(
        max_length=20,
        unique=True,
        choices=SLUG_CHOICES,
        primary_key=True,
        verbose_name="Identificador Plan"
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre del Plan"
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción"
    )
    limite_empresas = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Límite de Empresas"
    )
    limite_usuarios = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Límite de Usuarios por Empresa"
    )
    permite_aging_report = models.BooleanField(
        default=False,
        verbose_name="Permite Aging Report"
    )
    permite_alertas = models.BooleanField(
        default=False,
        verbose_name="Permite Alertas"
    )
    permite_simulaciones_avanzadas = models.BooleanField(
        default=False,
        verbose_name="Permite Simulaciones Avanzadas"
    )
    permite_importacion_frontend = models.BooleanField(
        default=False,
        verbose_name="Permite Importación Frontend"
    )
    permite_api = models.BooleanField(
        default=False,
        verbose_name="Permite Acceso API"
    )
    soporte_prioritario = models.BooleanField(
        default=False,
        verbose_name="Soporte Prioritario"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="¿Plan Disponible?"
    )

    class Meta:
        verbose_name = "Plan de Suscripción"
        verbose_name_plural = "Planes de Suscripción"
        ordering = ['limite_empresas', 'nombre']

    def __str__(self):
        return self.nombre


class SuscripcionEmpresa(models.Model):
    """
    Vincula una Empresa a un Plan específico.
    """
    empresa = models.OneToOneField(
        Empresa,
        on_delete=models.CASCADE,
        related_name="suscripcion",
        primary_key=True,
        verbose_name="Empresa"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="suscripciones",
        verbose_name="Plan Asignado"
    )
    fecha_inicio = models.DateField(
        default=timezone.now,
        verbose_name="Fecha Inicio Suscripción"
    )
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Fin Suscripción (si aplica)"
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="¿Suscripción Activa?"
    )

    class Meta:
        verbose_name = "Suscripción de Empresa"
        verbose_name_plural = "Suscripciones de Empresas"
        ordering = ['empresa__razon_social']

    def __str__(self):
        estado = "Activa" if self.activa else "Inactiva"
        return f"{self.empresa.razon_social} - Plan: {self.plan.nombre} ({estado})"

    def is_valid(self):
        """
        Verifica si la suscripción está vigente.
        """
        if not self.activa:
            return False
        if self.fecha_fin and self.fecha_fin < timezone.now().date():
            return False
        return True

    @property
    def permite_aging_report(self):
        return self.plan.permite_aging_report

    @property
    def limite_usuarios(self):
        return self.plan.limite_usuarios