# gestion/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
# --- AÑADE ESTA LÍNEA ---
from django.core.validators import MinValueValidator, MaxValueValidator
# --- FIN AÑADIR ---
from dateutil.relativedelta import relativedelta
import math
from decimal import Decimal # Asegúrate que Decimal esté importado si no lo estaba ya
from taggit.managers import TaggableManager # <-- Añadir
from core.models import Empresa

# Modelo para Clientes
class Cliente(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='clientes', verbose_name="Empresa")
    identificacion = models.CharField(max_length=50, unique=True, verbose_name="Identificación (NIT, RUT, CUIT, etc.)")
    nombre = models.CharField(max_length=255, verbose_name="Nombre o Razón Social")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Correo Electrónico")
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección")
    pais = models.CharField(max_length=100, blank=True, null=True, verbose_name="País") # Podría autocompletarse o heredar
    tags = TaggableManager(blank=True, verbose_name="Etiquetas / Categorías")

    # Campos de auditoría
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='clientes_creados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Creado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='clientes_actualizados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return f"{self.nombre} ({self.identificacion})"

    class Meta:
        unique_together = ('empresa', 'identificacion')
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['empresa__razon_social', 'nombre'] # Ordenar primero por empresa
    
    # gestion/models.py (continuación)

class Contacto(models.Model):
    # Relación: Un contacto puede pertenecer a UN Cliente O a UN Proveedor
    # Usaremos ForeignKeys opcionales. Una alternativa sería usar GenericForeignKey
    # pero para empezar, esto es más simple si un contacto NO pertenece a ambos.
    cliente = models.ForeignKey(
         'Cliente',
        on_delete=models.CASCADE, # Si se borra el cliente, se borran sus contactos
        null=True, blank=True,
        related_name='contactos'
    )
    proveedor = models.ForeignKey(
        'Proveedor',
        on_delete=models.CASCADE, # Si se borra el proveedor, se borran sus contactos
        null=True, blank=True,
        related_name='contactos'
    )

    # Datos del Contacto
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Contacto")
    cargo = models.CharField(max_length=150, blank=True, null=True, verbose_name="Cargo")
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Correo Electrónico")
    telefono_directo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono Directo")
    celular = models.CharField(max_length=50, blank=True, null=True, verbose_name="Celular / Móvil")
    es_principal = models.BooleanField(default=False, verbose_name="¿Es Contacto Principal?")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")

    # Campos de Auditoría (Simplificados para el contacto)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Validación para asegurar que el contacto pertenece a Cliente O Proveedor, no ambos ni ninguno
    def clean(self):
        if self.cliente and self.proveedor:
            raise ValidationError("Un contacto no puede pertenecer simultáneamente a un Cliente y a un Proveedor.")
        if not self.cliente and not self.proveedor:
             raise ValidationError("El contacto debe estar asociado a un Cliente o a un Proveedor.")
         # Podríamos añadir validación para asegurar que solo haya UN contacto principal por cliente/proveedor

    def __str__(self):
        asociado_a = ""
        if self.cliente:
            asociado_a = f" (Cliente: {self.cliente.nombre})"
        elif self.proveedor:
            asociado_a = f" (Proveedor: {self.proveedor.nombre})"
        return f"{self.nombre}{asociado_a}"

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        ordering = ['cliente', 'proveedor', '-es_principal', 'nombre'] # Ordenar por cliente/prov, principal primero

# Modelo para el registro general del Cobro (Factura/Venta)
class Cobro(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='cobros', verbose_name="Empresa")
    # --- Constantes para Choices ---
    class TipoVenta(models.TextChoices):
        PRODUCTO = 'PROD', 'Venta de Producto'
        SERVICIO = 'SERV', 'Prestación de Servicio'
        MIXTO = 'MIXT', 'Mixto (Producto y Servicio)'
        OTRO = 'OTRO', 'Otro'

    class EstatusCobro(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente'
        PAGADO_PARCIAL = 'PARC', 'Pagado Parcialmente'
        PAGADO_TOTAL = 'PAGA', 'Pagado Totalmente'
        VENCIDO = 'VENC', 'Vencido'
        ANULADO = 'ANUL', 'Anulado' # Añadido: útil para facturas canceladas

    # --- Relaciones ---
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='cobros', verbose_name="Cliente") # PROTECT para no borrar cliente con cobros
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='ventas_realizadas',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vendedor"
    )
    responsable_seguimiento = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='cobros_en_seguimiento',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsable de Seguimiento"
    )
    venta_proyectada_origen = models.ForeignKey( # <-- NUEVO: Vinculación
        'VentaProyectada',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cobros_generados',
        verbose_name="Venta Proyectada Origen"
    )


    # --- Datos de la Factura/Documento ---
    grupo_concepto = models.CharField(max_length=150, blank=True, verbose_name="Grupo o Concepto General")
    pais_cobro = models.CharField(max_length=100, blank=True, verbose_name="País del Cobro") # Podría heredar de Cliente o Empresa
    fecha_factura = models.DateField(verbose_name="Fecha Factura/Contrato/OC")
    numero_documento = models.CharField(max_length=100, verbose_name="Nº Factura/Documento", help_text="Número único del documento emitido") # Considerar unique=True si aplica
    producto_vendido_desc = models.TextField(blank=True, verbose_name="Descripción Productos/Servicios") # Descripción general
    tipo_venta = models.CharField(max_length=4, choices=TipoVenta.choices, default=TipoVenta.PRODUCTO, verbose_name="Tipo de Venta")
    adjunto_factura = models.FileField( # <-- NUEVO: Adjunto
        upload_to='facturas_cobros/',
        null=True, blank=True,
        verbose_name="Adjunto (Factura/Doc)"
    )

    # --- Valores Monetarios ---
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Subtotal")
    impuestos = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Impuestos")
    total_factura = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Total Factura", editable=False) # Se calculará
    moneda = models.CharField( # <-- NUEVO CAMPO (o modificar si ya existía)
        max_length=3,
        verbose_name="Moneda Transacción (ISO 4217)",
        help_text="Moneda de esta factura específica (ej: USD, EUR)",
        # Podríamos poner un default basado en la empresa o dejarlo obligatorio
        # default='USD' # Opcional
    )
    # --- Información de Pago y Seguimiento ---
    numero_cuotas = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)], # Validador existente
        verbose_name="Número de Cuotas",
        help_text="Máximo 12. Las cuotas se generarán automáticamente al guardar." # Ayuda actualizada
    )
    # La fecha esperada y real de CADA cuota va en DetalleCuotaCobro
    fecha_vencimiento_inicial = models.DateField(null=True, blank=True, verbose_name="Fecha Vencimiento (Inicial)") # Fecha de la primera cuota o única
    fecha_ultimo_seguimiento = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Último Seguimiento")
    estatus = models.CharField(max_length=4, choices=EstatusCobro.choices, default=EstatusCobro.PENDIENTE, verbose_name="Estatus General")
    comentarios = models.TextField(blank=True, verbose_name="Comentarios / Observaciones")

    # --- Campos de Auditoría ---
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='cobros_creados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Creado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='cobros_actualizados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    # --- Métodos y Propiedades ---
    def save(self, *args, **kwargs):
        is_new = self.pk is None # Comprobar si es un objeto nuevo
        # Calcular total antes de guardar (lógica existente)
        self.total_factura = (self.subtotal or 0) + (self.impuestos or 0)

        super().save(*args, **kwargs) # Guardar primero el objeto Cobro para tener un ID (pk)

        # --- Generación automática de cuotas (SOLO si es nuevo y tiene más de 0 cuotas) ---
        if is_new and self.numero_cuotas > 0 and not self.cuotas.exists():
            monto_total = self.total_factura
            monto_por_cuota = round(monto_total / self.numero_cuotas, 2)
            monto_acumulado = Decimal('0.00')
            fecha_vencimiento_cuota = self.fecha_vencimiento_inicial or timezone.now().date() # Usar fecha inicial o hoy

            for i in range(1, self.numero_cuotas + 1):
                monto_actual = monto_por_cuota
                # Ajustar la última cuota para que la suma sea exacta
                if i == self.numero_cuotas:
                    monto_actual = monto_total - monto_acumulado

                DetalleCuotaCobro.objects.create(
                    cobro=self,
                    numero_cuota=i,
                    monto_cuota=monto_actual,
                    fecha_vencimiento=fecha_vencimiento_cuota,
                    estatus=DetalleCuotaCobro.EstatusCuota.PENDIENTE
                )
                monto_acumulado += monto_actual

                # Calcular la fecha de la siguiente cuota (asumiendo 30 días como default por ahora)
                # Mejora: Hacer el intervalo configurable o más inteligente (ej: mensual)
                # ¡Usando relativedelta para sumar meses correctamente!
                if self.numero_cuotas > 1: # Solo calcular si hay más de una cuota
                    # Asumamos lógica mensual por defecto si fecha_vencimiento_inicial tiene día
                    if self.fecha_vencimiento_inicial:
                       fecha_vencimiento_cuota += relativedelta(months=1)
                    else: # Si no hay fecha inicial, sumamos 30 días como fallback
                       fecha_vencimiento_cuota += timedelta(days=30)

    @property
    def antiguedad(self):
        """Calcula la antigüedad en días desde la fecha de factura hasta hoy."""
        if self.fecha_factura:
            return (timezone.now().date() - self.fecha_factura).days
        return None # O 0 si se prefiere

    @property
    def esta_vencido(self):
        """Determina si la fecha de vencimiento inicial ya pasó (simplificado)."""
        if self.estatus in [self.EstatusCobro.PAGADO_TOTAL, self.EstatusCobro.ANULADO]:
            return False
        if self.fecha_vencimiento_inicial:
            return timezone.now().date() > self.fecha_vencimiento_inicial
        return False # Si no hay fecha de vencimiento, no se considera vencido aún

    def __str__(self):
        return f"Cobro {self.numero_documento} a {self.cliente.nombre} - Total: {self.total_factura}"

    class Meta:
        verbose_name = "Registro de Cobro"
        verbose_name_plural = "Registros de Cobros"
        ordering = ['empresa__razon_social','-fecha_factura', 'numero_documento'] # Ordenar por empresa, luego fecha descendente, luego por número
        indexes = [ # Sugerencia: Índices para campos comunes de búsqueda/filtrado
            models.Index(fields=['cliente']),
            models.Index(fields=['fecha_factura']),
            models.Index(fields=['estatus']),
        ]

        # gestion/models.py (continuación)

# Modelo para cada Cuota de un Cobro
class DetalleCuotaCobro(models.Model):
    # --- Constantes para Choices ---
    class EstatusCuota(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente'
        PAGADA = 'PAGA', 'Pagada'
        VENCIDA = 'VENC', 'Vencida' # Podría actualizarse automáticamente
        ANULADA = 'ANUL', 'Anulada'

    # --- Relación ---
    cobro = models.ForeignKey(Cobro, on_delete=models.CASCADE, related_name='cuotas', verbose_name="Cobro Asociado")
   
    # --- Datos de la Cuota ---
    numero_cuota = models.PositiveSmallIntegerField(verbose_name="Nº Cuota")
    monto_cuota = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto de la Cuota")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de Vencimiento")
    fecha_pago_real = models.DateField(null=True, blank=True, verbose_name="Fecha Real de Pago")
    estatus = models.CharField(max_length=4, choices=EstatusCuota.choices, default=EstatusCuota.PENDIENTE, verbose_name="Estatus Cuota")
    # --- NUEVOS CAMPOS ---
    cuenta_bancaria_deposito = models.ForeignKey( # A qué cuenta entró el dinero
        'CuentaBancaria', # Usar string por si CuentaBancaria está definida después
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='depositos_recibidos',
        verbose_name="Cuenta Bancaria Depósito"
    )
    numero_retencion = models.CharField( # Número del documento de retención
        max_length=100,
        blank=True, null=True,
        verbose_name="Nº Retención Fiscal"
    )
    valor_retencion = models.DecimalField( # Monto retenido en esta cuota
        max_digits=15, decimal_places=2,
        default=Decimal('0.00'), # Por defecto no hay retención
        verbose_name="Valor Retención Fiscal"
    )
    # --------------------
    observaciones_cuota = models.TextField(blank=True, verbose_name="Observaciones Específicas de la Cuota")

    # --- Campos de Auditoría (simplificados para la cuota, opcional) ---
    # creado_en = models.DateTimeField(auto_now_add=True)
    # actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def dias_vencida(self):
        """Calcula cuántos días han pasado desde el vencimiento si está pendiente."""
        if self.estatus == self.EstatusCuota.PENDIENTE and timezone.now().date() > self.fecha_vencimiento:
            return (timezone.now().date() - self.fecha_vencimiento).days
        return 0
    @property
    def valor_real_cobrado(self): # <-- NUEVA PROPIEDAD CALCULADA
        """Calcula el monto neto recibido (Monto Cuota - Retención)."""
        return (self.monto_cuota or Decimal('0.00')) - (self.valor_retencion or Decimal('0.00'))
    
    def __str__(self):
         # Actualizar str para más claridad
         return f"Cuota {self.numero_cuota}/{self.cobro.numero_cuotas} de {self.cobro.numero_documento} - Neto: {self.valor_real_cobrado} - Vence: {self.fecha_vencimiento}"
    
    class Meta:
        verbose_name = "Detalle de Cuota de Cobro"
        verbose_name_plural = "Detalles de Cuotas de Cobros"
        ordering = ['cobro', 'numero_cuota'] # Ordenar por cobro, luego por número de cuota
        unique_together = ('cobro', 'numero_cuota') # No puede haber dos cuotas con el mismo número para el mismo cobro
        indexes = [
            models.Index(fields=['cobro']),
            models.Index(fields=['fecha_vencimiento']),
            models.Index(fields=['estatus']),
        ]
# gestion/models.py (continuación)

# Modelo para Proveedores
class Proveedor(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='proveedores', verbose_name="Empresa")
    identificacion = models.CharField(max_length=50, unique=True, verbose_name="Identificación (NIT, RUT, CUIT, etc.)")
    nombre = models.CharField(max_length=255, verbose_name="Nombre o Razón Social")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Correo Electrónico")
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección")
    pais = models.CharField(max_length=100, blank=True, null=True, verbose_name="País")
    tags = TaggableManager(blank=True, verbose_name="Etiquetas / Categorías")
    # Podríamos añadir campos como 'datos_bancarios', 'contacto_principal', etc. si es necesario

    # Campos de auditoría
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='proveedores_creados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Creado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='proveedores_actualizados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return f"{self.nombre} ({self.identificacion})"

    class Meta:
        unique_together = ('empresa', 'identificacion')
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['empresa__razon_social','nombre']

class Contacto(models.Model):
    # Relación: Un contacto puede pertenecer a UN Cliente O a UN Proveedor
    # Usaremos ForeignKeys opcionales. Una alternativa sería usar GenericForeignKey
    # pero para empezar, esto es más simple si un contacto NO pertenece a ambos.
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE, # Si se borra el cliente, se borran sus contactos
        null=True, blank=True,
        related_name='contactos'
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE, # Si se borra el proveedor, se borran sus contactos
        null=True, blank=True,
        related_name='contactos'
    )

    # Datos del Contacto
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Contacto")
    cargo = models.CharField(max_length=150, blank=True, null=True, verbose_name="Cargo")
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Correo Electrónico")
    telefono_directo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono Directo")
    celular = models.CharField(max_length=50, blank=True, null=True, verbose_name="Celular / Móvil")
    es_principal = models.BooleanField(default=False, verbose_name="¿Es Contacto Principal?")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")

    # Campos de Auditoría (Simplificados para el contacto)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Validación para asegurar que el contacto pertenece a Cliente O Proveedor, no ambos ni ninguno
    def clean(self):
        if self.cliente and self.proveedor:
            raise ValidationError("Un contacto no puede pertenecer simultáneamente a un Cliente y a un Proveedor.")
        if not self.cliente and not self.proveedor:
             raise ValidationError("El contacto debe estar asociado a un Cliente o a un Proveedor.")
         # Podríamos añadir validación para asegurar que solo haya UN contacto principal por cliente/proveedor

    def __str__(self):
        asociado_a = ""
        if self.cliente:
            asociado_a = f" (Cliente: {self.cliente.nombre})"
        elif self.proveedor:
            asociado_a = f" (Proveedor: {self.proveedor.nombre})"
        return f"{self.nombre}{asociado_a}"

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        ordering = ['cliente', 'proveedor', '-es_principal', 'nombre'] # Ordenar por cliente/prov, principal primero

# gestion/models.py (continuación)
from django.core.validators import MaxValueValidator, MinValueValidator # Para validar número de cuotas

# Modelo para el registro general del Pago a Proveedor (Factura/Compra)
class Pago(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='pagos', verbose_name="Empresa")
    # --- Constantes para Choices ---
    class TipoCompra(models.TextChoices):
        BIENES = 'BIEN', 'Compra de Bienes'
        SERVICIOS = 'SERV', 'Contratación de Servicios'
        ACTIVOS = 'ACTI', 'Adquisición de Activos'
        GASTO = 'GAST', 'Gasto Operativo' # Relacionado a factura, no recurrente
        IMPUESTO = 'IMPU', 'Pago de Impuestos'
        OTRO = 'OTRO', 'Otro'

    class EstatusPago(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente de Pago'
        PAGADO_PARCIAL = 'PARC', 'Pagado Parcialmente'
        PAGADO_TOTAL = 'PAGA', 'Pagado Totalmente'
        VENCIDO = 'VENC', 'Vencido' # Podría ser un estado o una condición
        ANULADO = 'ANUL', 'Anulado'

    # --- Relaciones ---
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='pagos_a_realizar', verbose_name="Proveedor")
    responsable_pago = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='pagos_asignados',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsable de Realizar Pago"
    )

    # --- Datos de la Factura/Documento ---
    grupo_concepto = models.CharField(max_length=150, blank=True, verbose_name="Grupo o Concepto General del Pago")
    fecha_emision_factura = models.DateField(verbose_name="Fecha Emisión Factura Proveedor")
    pais_proveedor = models.CharField(max_length=100, blank=True, verbose_name="País del Proveedor") # Se puede autocompletar desde el proveedor
    numero_documento = models.CharField(max_length=100, verbose_name="Nº Factura/Documento del Proveedor")
    tipo_compra = models.CharField(max_length=4, choices=TipoCompra.choices, default=TipoCompra.BIENES, verbose_name="Tipo de Compra/Gasto")
    adjunto_documento = models.FileField( # <-- NUEVO: Adjunto
        upload_to='facturas_pagos/',
        null=True, blank=True,
        verbose_name="Adjunto (Factura/Doc)"
    )
    # --- Valores Monetarios ---
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Subtotal")
    impuestos = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Impuestos")
    total_factura = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Total a Pagar", editable=False) # Se calculará
    moneda = models.CharField( # <-- NUEVO CAMPO (o modificar si ya existía)
        max_length=3,
        verbose_name="Moneda Transacción (ISO 4217)",
        help_text="Moneda de esta factura específica (ej: USD, EUR)",
        # Podríamos poner un default basado en la empresa o dejarlo obligatorio
        # default='USD' # Opcional
    )
    # --- Información de Pago ---
    numero_cuotas = models.PositiveSmallIntegerField( # Actualizar help_text
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name="Número de Cuotas a Pagar",
        help_text="Máximo 12. Las cuotas se generarán automáticamente al guardar."
    )
    # La fecha de CADA cuota va en DetalleCuotaPago
    fecha_vencimiento_inicial = models.DateField(null=True, blank=True, verbose_name="Fecha Vencimiento (Inicial/Única)")
    estatus = models.CharField(max_length=4, choices=EstatusPago.choices, default=EstatusPago.PENDIENTE, verbose_name="Estatus General del Pago")
    comentarios = models.TextField(blank=True, verbose_name="Comentarios / Observaciones")

    # --- Campos de Auditoría ---
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='pagos_creados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Registrado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='pagos_actualizados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    # --- Métodos y Propiedades ---
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Calcular total y autocompletar país (lógica existente)
        self.total_factura = (self.subtotal or 0) + (self.impuestos or 0)
        if self.proveedor and not self.pais_proveedor:
            self.pais_proveedor = self.proveedor.pais

        super().save(*args, **kwargs) # Guardar primero el objeto Pago

        # --- Generación automática de cuotas (SOLO si es nuevo y tiene > 0 cuotas) ---
        if is_new and self.numero_cuotas > 0 and not self.cuotas_pago.exists():
            monto_total = self.total_factura
            monto_por_cuota = round(monto_total / self.numero_cuotas, 2)
            monto_acumulado = Decimal('0.00')
            fecha_vencimiento_cuota = self.fecha_vencimiento_inicial or timezone.now().date()

            for i in range(1, self.numero_cuotas + 1):
                monto_actual = monto_por_cuota
                if i == self.numero_cuotas:
                    monto_actual = monto_total - monto_acumulado

                DetalleCuotaPago.objects.create(
                    pago=self,
                    numero_cuota=i,
                    monto_cuota=monto_actual,
                    fecha_vencimiento=fecha_vencimiento_cuota,
                    estatus=DetalleCuotaPago.EstatusCuotaPago.PENDIENTE
                )
                monto_acumulado += monto_actual

                if self.numero_cuotas > 1:
                    if self.fecha_vencimiento_inicial:
                        fecha_vencimiento_cuota += relativedelta(months=1)
                    else:
                        fecha_vencimiento_cuota += timedelta(days=30)
    @property
    def antiguedad_emision(self):
        """Días desde la emisión de la factura."""
        if self.fecha_emision_factura:
            return (timezone.now().date() - self.fecha_emision_factura).days
        return None

    # La antigüedad del VENCIMIENTO se manejará a nivel de cuota

    def __str__(self):
        return f"Pago {self.numero_documento} a {self.proveedor.nombre} - Total: {self.total_factura}"

    class Meta:
        verbose_name = "Registro de Pago a Proveedor"
        verbose_name_plural = "Registros de Pagos a Proveedores"
        ordering = ['empresa__razon_social','-fecha_vencimiento_inicial', 'fecha_emision_factura'] # Priorizar vencimientos próximos
        indexes = [
            models.Index(fields=['proveedor']),
            models.Index(fields=['fecha_emision_factura']),
            models.Index(fields=['fecha_vencimiento_inicial']),
            models.Index(fields=['estatus']),
        ]
# gestion/models.py (continuación)

# Modelo para cada Cuota de un Pago a Proveedor
class DetalleCuotaPago(models.Model):
    # --- Constantes para Choices ---
    class EstatusCuotaPago(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente'
        PAGADA = 'PAGA', 'Pagada'
        VENCIDA = 'VENC', 'Vencida' # Estado o condición
        ANULADA = 'ANUL', 'Anulada'

    # --- Relación ---
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name='cuotas_pago', verbose_name="Pago Asociado")

    # --- Datos de la Cuota ---
    numero_cuota = models.PositiveSmallIntegerField(verbose_name="Nº Cuota")
    monto_cuota = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto de la Cuota")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de Vencimiento (Pago Tentativo)")
    fecha_pago_real = models.DateField(null=True, blank=True, verbose_name="Fecha Real de Pago")
    estatus = models.CharField(max_length=4, choices=EstatusCuotaPago.choices, default=EstatusCuotaPago.PENDIENTE, verbose_name="Estatus Cuota")
    observaciones_cuota = models.TextField(blank=True, verbose_name="Observaciones Específicas de la Cuota")

    # --- Campos de Auditoría (Opcional) ---
    # Podrían heredar del Pago principal o tener los suyos propios si se modifican individualmente con frecuencia

    @property
    def antiguedad_vencimiento(self):
        """Días transcurridos desde el vencimiento si está pendiente/vencida."""
        if self.estatus in [self.EstatusCuotaPago.PENDIENTE, self.EstatusCuotaPago.VENCIDA] and timezone.now().date() > self.fecha_vencimiento:
            return (timezone.now().date() - self.fecha_vencimiento).days
        return 0 # No está vencida o ya se pagó/anuló

    def __str__(self):
        return f"Cuota {self.numero_cuota} de Pago {self.pago.numero_documento} - Vence: {self.fecha_vencimiento}"

    class Meta:
        verbose_name = "Detalle de Cuota de Pago"
        verbose_name_plural = "Detalles de Cuotas de Pagos"
        ordering = ['pago', 'numero_cuota']
        unique_together = ('pago', 'numero_cuota')
        indexes = [
            models.Index(fields=['pago']),
            models.Index(fields=['fecha_vencimiento']),
            models.Index(fields=['estatus']),
        ]
# gestion/models.py (continuación)

# Modelo para la plantilla de Gastos Recurrentes
class GastoRecurrente(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='gastosrecurrentes', verbose_name="Empresa")

    class FrecuenciaGasto(models.TextChoices):
        DIARIO = 'DIA', 'Diario'
        SEMANAL = 'SEM', 'Semanal'
        QUINCENAL = 'QUI', 'Quincenal' # Cada 15 días exactos o días 15 y fin de mes? Aclarar lógica si es necesario. Asumamos cada 15 días por ahora.
        MENSUAL = 'MES', 'Mensual'
        BIMESTRAL = 'BIM', 'Bimestral'
        TRIMESTRAL = 'TRI', 'Trimestral'
        SEMESTRAL = 'SME', 'Semestral'
        ANUAL = 'ANU', 'Anual'
        UNICA_VEZ = 'UNI', 'Única Vez' # Aunque es recurrente, puede tener fin

    # --- Datos del Gasto ---
    grupo_concepto = models.CharField(max_length=150, verbose_name="Grupo o Concepto del Gasto")
    descripcion = models.TextField(verbose_name="Descripción del Gasto")
    monto_base = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor Base a Pagar")
    moneda = models.CharField(max_length=3, default='USD', verbose_name="Moneda") # Asumir una default o heredar de Empresa

    # --- Programación ---
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio (Primer Pago)")
    frecuencia = models.CharField(max_length=3, choices=FrecuenciaGasto.choices, verbose_name="Repetición del Pago")
    dia_del_mes = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(31)], verbose_name="Día del Mes (si aplica)", help_text="Para pagos mensuales/bimestrales/etc. especificar el día.")
    fecha_fin = models.DateField(null=True, blank=True, verbose_name="Fecha Final del Pago (Opcional)")

    # --- Responsabilidad y Estado ---
    responsable_pago = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='gastos_recurrentes_asignados',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsable de Realizar Pago"
    )
    activo = models.BooleanField(default=True, verbose_name="¿Está Activo?") # Para poder 'pausar' la generación de ocurrencias
    comentarios = models.TextField(blank=True, verbose_name="Comentarios / Observaciones")

    # --- Campos de Auditoría ---
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='gastos_recurrentes_creados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Registrado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='gastos_recurrentes_actualizados',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def __str__(self):
        return f"{self.descripcion} ({self.get_frecuencia_display()}) - {self.monto_base} {self.moneda}"

    class Meta:
        verbose_name = "Gasto Recurrente (Plantilla)"
        verbose_name_plural = "Gastos Recurrentes (Plantillas)"
        ordering = ['empresa__razon_social','grupo_concepto', 'descripcion']

# gestion/models.py (continuación)

# Modelo para cada ocurrencia específica de un Gasto Recurrente
class OcurrenciaGasto(models.Model):
    class EstatusOcurrencia(models.TextChoices):
        PENDIENTE = 'PEND', 'Pendiente'
        PAGADO = 'PAGA', 'Pagado'
        VENCIDO = 'VENC', 'Vencido' # Estado o condición
        ANULADO = 'ANUL', 'Anulado' # Si una ocurrencia específica se cancela

    # --- Relación ---
    gasto_recurrente = models.ForeignKey(GastoRecurrente, on_delete=models.CASCADE, related_name='ocurrencias', verbose_name="Gasto Recurrente Asociado")

    # --- Datos de la Ocurrencia ---
    fecha_vencimiento = models.DateField(verbose_name="Fecha Tentativa de Pago")
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto a Pagar") # Puede diferir del base si hay ajustes
    estatus = models.CharField(max_length=4, choices=EstatusOcurrencia.choices, default=EstatusOcurrencia.PENDIENTE, verbose_name="Estado")
    fecha_pago_real = models.DateField(null=True, blank=True, verbose_name="Fecha Real de Pago")
    comentarios = models.TextField(blank=True, verbose_name="Comentarios Específicos de la Ocurrencia")

    # --- Campos de Auditoría (Simplificados o heredados) ---
    # Quien paga es el responsable en GastoRecurrente, o podríamos añadirlo aquí si cambia
    pagado_por = models.ForeignKey(
         settings.AUTH_USER_MODEL, related_name='ocurrencias_pagadas',
         on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Pagado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación Ocurrencia") # Cuando se generó el registro
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización Ocurrencia")

    @property
    def antiguedad_vencimiento(self):
        """Días transcurridos desde el vencimiento si está pendiente/vencida."""
        if self.estatus in [self.EstatusOcurrencia.PENDIENTE, self.EstatusOcurrencia.VENCIDO] and timezone.now().date() > self.fecha_vencimiento:
            return (timezone.now().date() - self.fecha_vencimiento).days
        return 0

    def __str__(self):
        return f"Ocurrencia de '{self.gasto_recurrente.descripcion}' - Vence: {self.fecha_vencimiento} - Estado: {self.get_estatus_display()}"

    class Meta:
        verbose_name = "Ocurrencia de Gasto Recurrente"
        verbose_name_plural = "Ocurrencias de Gastos Recurrentes"
        ordering = ['fecha_vencimiento', 'gasto_recurrente']
        indexes = [
            models.Index(fields=['gasto_recurrente']),
            models.Index(fields=['fecha_vencimiento']),
            models.Index(fields=['estatus']),
        ]

# gestion/models.py (continuación)
from django.core.validators import MinValueValidator, MaxValueValidator # Para el % de margen

# Modelo para Ventas Proyectadas / Oportunidades
class VentaProyectada(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='ventasproyectadas', verbose_name="Empresa")
    moneda = models.CharField(max_length=3, default='USD', verbose_name="Moneda Venta Proyectada")
    class EstatusVenta(models.TextChoices):
        PROSPECTO = 'PROS', 'Prospecto'
        CALIFICADO = 'CALI', 'Calificado'
        PROPUESTA = 'PROP', 'Propuesta Enviada'
        NEGOCIACION = 'NEGO', 'En Negociación'
        GANADA = 'GANA', 'Ganada (Pendiente Facturar)' # Estado previo a convertirse en Cobro
        PERDIDA = 'PERD', 'Perdida'
        APLAZADA = 'APLA', 'Aplazada'

    # --- Relaciones ---
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_proyectadas', verbose_name="Cliente Potencial")
    asesor_comercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='proyecciones_asignadas',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Asesor Comercial"
    )
    responsable_seguimiento = models.ForeignKey( # Corregido de 'responsable pago'
        settings.AUTH_USER_MODEL, related_name='proyecciones_en_seguimiento',
        on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsable Seguimiento"
    )

    # --- Datos de la Proyección ---
    grupo_concepto = models.CharField(max_length=150, blank=True, verbose_name="Grupo o Concepto de la Venta")
    codigo_oportunidad = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="Código Oportunidad", help_text="Código único si aplica")
    estatus = models.CharField(max_length=4, choices=EstatusVenta.choices, default=EstatusVenta.PROSPECTO, verbose_name="Estatus")
    pais_venta = models.CharField(max_length=100, blank=True, verbose_name="País de la Venta") # Podría heredar de Cliente
    descripcion = models.TextField(blank=True, verbose_name="Descripción de la Venta")

    # --- Valores Estimados ---
    valor_total_estimado = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Valor Total Estimado")
    porcentaje_margen = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="% Margen Estimado", help_text="Valor entre 0 y 100"
    )
    margen_estimado = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Margen Estimado ($)", editable=False) # Calculado

    # --- Fecha y Comentarios ---
    fecha_cierre_estimada = models.DateField(verbose_name="Fecha Estimada de Cierre")
    comentarios = models.TextField(blank=True, verbose_name="Comentarios / Observaciones")

    # --- Campos de Auditoría ---
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='ventas_proyectadas_creadas',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Registrado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='ventas_proyectadas_actualizadas',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Actualizado por"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    def save(self, *args, **kwargs):
        # Calcular margen antes de guardar
        if self.valor_total_estimado is not None and self.porcentaje_margen is not None:
            self.margen_estimado = self.valor_total_estimado * (self.porcentaje_margen / 100)
        else:
            self.margen_estimado = 0
        # Autocompletar país si está vacío y hay cliente
        if self.cliente and not self.pais_venta:
             self.pais_venta = self.cliente.pais
        super().save(*args, **kwargs)
    @property
    def probabilidad_asignada(self): # <-- NUEVA PROPIEDAD
        """Devuelve la probabilidad (%) asociada al estatus actual."""
        probabilidades = {
            self.EstatusVenta.PROSPECTO: 10,
            self.EstatusVenta.CALIFICADO: 25,
            self.EstatusVenta.PROPUESTA: 50,
            self.EstatusVenta.NEGOCIACION: 75,
            self.EstatusVenta.GANADA: 100, # Ganada = 100%
            self.EstatusVenta.PERDIDA: 0,
            self.EstatusVenta.APLAZADA: 15, # Podría ser configurable o basado en nueva fecha
        }
        return probabilidades.get(self.estatus, 0) # Devuelve 0 si el estatus no está mapeado

    @property
    def valor_ponderado(self): # <-- NUEVA PROPIEDAD
        """Calcula el valor total estimado ponderado por la probabilidad del estatus."""
        valor = self.valor_total_estimado or Decimal('0.00')
        probabilidad = Decimal(self.probabilidad_asignada) / 100
        return valor * probabilidad

    def __str__(self):
        cliente_nombre = self.cliente.nombre if self.cliente else "Sin Cliente Asignado"
        return f"Proyección: {self.descripcion[:50]}... ({cliente_nombre}) - Cierre: {self.fecha_cierre_estimada}"

    class Meta:
        verbose_name = "Venta Proyectada / Oportunidad"
        verbose_name_plural = "Ventas Proyectadas / Oportunidades"
        ordering = ['empresa__razon_social','fecha_cierre_estimada', 'estatus']
        indexes = [
            models.Index(fields=['cliente']),
            models.Index(fields=['fecha_cierre_estimada']),
            models.Index(fields=['estatus']),
            models.Index(fields=['asesor_comercial']),
        ]

# gestion/models.py (continuación)

# Modelo para Cuentas Bancarias y sus Saldos
class CuentaBancaria(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='cuentasbancarias', verbose_name="Empresa")
    nombre_banco = models.CharField(max_length=150, verbose_name="Nombre del Banco")
    numero_cuenta = models.CharField(max_length=100, unique=True, verbose_name="Número de Cuenta / Alias") # unique=True para evitar duplicados
    moneda = models.CharField(max_length=3, default='USD', verbose_name="Moneda Cuenta") # Ajustar default según necesidad
    saldo_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0.00, verbose_name="Saldo Actual")

    # Campos de Auditoría (actualizado_en es la fecha de última actualización del saldo)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='cuentas_bancarias_creadas',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Registrado por"
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='cuentas_bancarias_actualizadas',
        on_delete=models.SET_NULL, null=True, blank=True, editable=False, verbose_name="Último en Actualizar Saldo"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro Cuenta")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Fecha Última Actualización Saldo") # Fecha de la última vez que se guardó/actualizó el saldo

    def __str__(self):
        return f"{self.nombre_banco} - {self.numero_cuenta} ({self.moneda})"

    class Meta:
        unique_together = ('empresa', 'numero_cuenta')
        verbose_name = "Cuenta Bancaria"
        verbose_name_plural = "Cuentas Bancarias"
        ordering = ['empresa__razon_social','nombre_banco', 'numero_cuenta']