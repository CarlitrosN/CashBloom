# gestion/admin.py
from django.contrib import admin
from .models import (
    Cliente, Cobro, DetalleCuotaCobro,
    Proveedor, Pago, DetalleCuotaPago,
    GastoRecurrente, OcurrenciaGasto,
    VentaProyectada, CuentaBancaria, Contacto
)
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import math
from django.utils.html import format_html
from django.urls import reverse
from taggit.models import Tag
from import_export.admin import ImportExportModelAdmin, ImportMixin, ExportMixin # Importar mixins también si se necesita granularidad
from import_export import resources # Para personalización si es necesaria
from django.forms.models import BaseInlineFormSet


# --- Definiciones de Recursos (Opcional: Para personalizar Import/Export) ---
# Si la configuración por defecto es suficiente, no necesitas definir estas clases Resource.
# class ClienteResource(resources.ModelResource):
#     class Meta:
#         model = Cliente
#         # fields = ('id', 'nombre', ...) # Especificar campos
#         # exclude = ('creado_por', ...) # Excluir campos
#         # skip_unchanged = True
#         # report_skipped = True

# --- Definiciones de Inlines ---

class ContactoInline(admin.TabularInline):
    model = Contacto
    extra = 1
    fields = ('nombre', 'cargo', 'email', 'telefono_directo', 'celular', 'es_principal', 'observaciones')
    # Validación para múltiples contactos principales
    def get_formset(self, request, obj=None, **kwargs):
        DefaultFormSet = super().get_formset(request, obj, **kwargs)
        parent_model = self.parent_model
        def clean(self):
             super(DefaultFormSet, self).clean()
             principales_count = 0
             for form in self.forms:
                 if self.can_delete and self._should_delete_form(form):
                     continue
                 is_principal = False
                 if form.is_valid() and form.cleaned_data.get('es_principal'):
                     is_principal = True
                 elif form.instance.pk and form.instance.es_principal and 'es_principal' not in form.changed_data:
                     is_principal = True
                 if is_principal:
                     principales_count += 1
             if principales_count > 1:
                 raise ValidationError(f"Solo puede haber un contacto marcado como principal para este {parent_model._meta.verbose_name}.")
        DefaultFormSet.clean = clean
        return DefaultFormSet

class DetalleCuotaCobroInline(admin.TabularInline):
    model = DetalleCuotaCobro
    extra = 0
    fields = ('numero_cuota', 'monto_cuota', 'valor_retencion', 'valor_real_cobrado_display',
              'fecha_vencimiento', 'estatus', 'fecha_pago_real',
              'cuenta_bancaria_deposito', 'numero_retencion',
              'observaciones_cuota')
    readonly_fields = ('numero_cuota', 'valor_real_cobrado_display',)
    ### MEJORA: Prefetch related para el ForeignKey de CuentaBancaria si se usa mucho
    # fk_name = 'cobro' # Necesario si hay más de un FK al padre

    def valor_real_cobrado_display(self, obj):
        return obj.valor_real_cobrado if obj else '-'
    valor_real_cobrado_display.short_description = 'Neto Cobrado'

class DetalleCuotaPagoInline(admin.TabularInline):
    model = DetalleCuotaPago
    extra = 0
    fields = ('numero_cuota', 'monto_cuota', 'fecha_vencimiento', 'fecha_pago_real', 'estatus', 'observaciones_cuota')
    readonly_fields = ('numero_cuota',)

# --- Registros de ModelAdmin ---

@admin.register(Cliente)
class ClienteAdmin(ImportExportModelAdmin):
    # resource_class = ClienteResource # Descomentar si definiste un Resource personalizado
    list_display = ('nombre', 'identificacion','empresa', 'telefono', 'email', 'pais', 'display_tags', 'actualizado_en')
    search_fields = ('nombre', 'identificacion', 'email', 'tags__name', 'contactos__nombre', 'contactos__email','empresa__razon_social') ### MEJORA: Buscar por contacto
    list_filter = ('empresa','pais', 'creado_en', 'tags') ### MEJORA: Filtrar por tags (requiere configuración extra o usar búsqueda) - quitado tag por E116
    list_filter = ('empresa','pais', 'creado_en') # Mantenemos sin filtro de tag directo por simplicidad
    readonly_fields = ('creado_por', 'creado_en', 'actualizado_por', 'actualizado_en')
    fieldsets = (
        (None, {'fields': ('empresa','identificacion', 'nombre', 'telefono', 'email', 'direccion', 'pais')}),
        ('Segmentación', {'fields': ('tags',)}),
        ('Auditoría', {'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')), 'classes': ('collapse',)})
    )
    inlines = [ContactoInline]
    list_select_related = ('creado_por', 'actualizado_por', 'empresa') ### MEJORA: Optimizar consulta para auditoría si se muestra

    def display_tags(self, obj):
        tags = getattr(obj, '_prefetched_tags_cache', None)
        if tags is None and hasattr(obj, 'tags'):
            try:
                if hasattr(obj.tags, 'all'): tags = obj.tags.all()
                else: tags = []
            except Exception: tags = []
        elif tags is None: tags = []
        return ", ".join(t.name for t in tags)
    display_tags.short_description = 'Etiquetas'

    # save_model ya estaba bien

@admin.register(Proveedor)
class ProveedorAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'identificacion','empresa', 'telefono', 'email', 'pais', 'display_tags', 'actualizado_en')
    search_fields = ('nombre', 'identificacion', 'email', 'tags__name', 'contactos__nombre', 'contactos__email', 'empresa__razon_social') ### MEJORA: Buscar por contacto
    list_filter = ('empresa','pais', 'creado_en') # Quitamos filtro de tags
    readonly_fields = ('creado_por', 'creado_en', 'actualizado_por', 'actualizado_en')
    fieldsets = (
         (None, {'fields': ('empresa','identificacion', 'nombre', 'telefono', 'email', 'direccion', 'pais')}),
         ('Segmentación', {'fields': ('tags',)}),
         ('Auditoría', {'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')), 'classes': ('collapse',)})
    )
    inlines = [ContactoInline]
    list_select_related = ('creado_por', 'actualizado_por', 'empresa') ### MEJORA

    display_tags = ClienteAdmin.display_tags # Reutilizar función
    display_tags.short_description = 'Etiquetas'

    # save_model ya estaba bien

@admin.register(Cobro)
class CobroAdmin(ImportExportModelAdmin): ### MEJORA: Habilitar Import/Export
    list_display = ('numero_documento', 'cliente','empresa', 'fecha_factura', 'total_factura', 'estatus', 'responsable_seguimiento', 'actualizado_en') ### MEJORA: Quitado 'antiguedad' por posible lentitud
    search_fields = ('numero_documento', 'cliente__nombre', 'cliente__identificacion', 'producto_vendido_desc', 'grupo_concepto','empresa__razon_social') ### MEJORA: Añadido grupo_concepto
    list_filter = ('empresa', 'estatus', 'tipo_venta', 'pais_cobro', 'fecha_factura', 'responsable_seguimiento', 'vendedor', 'cliente') ### MEJORA: Añadido cliente
    readonly_fields = ('total_factura', 'creado_por', 'creado_en', 'actualizado_por', 'actualizado_en', 'antiguedad') # Antiguedad sigue readonly
    date_hierarchy = 'fecha_factura' ### MEJORA: Navegación por fecha
    list_select_related = ('cliente', 'responsable_seguimiento', 'vendedor', 'creado_por', 'actualizado_por', 'venta_proyectada_origen') ### MEJORA: Optimizar FKs
    fieldsets = (
        (None, {'fields': ('empresa', 'cliente', 'venta_proyectada_origen', ('fecha_factura', 'numero_documento'), 'grupo_concepto', 'pais_cobro')}),
        ('Detalles Venta', {'fields': ('producto_vendido_desc', 'tipo_venta', 'vendedor', ('subtotal', 'impuestos', 'total_factura'))}),
        ('Pago y Seguimiento', {'fields': (('numero_cuotas', 'fecha_vencimiento_inicial'), 'estatus', 'responsable_seguimiento', 'fecha_ultimo_seguimiento', 'comentarios', 'adjunto_factura')}),
        ('Auditoría', {'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')), 'classes': ('collapse',)})
    )
    inlines = [DetalleCuotaCobroInline]
    list_select_related = ('cliente', 'responsable_seguimiento', 'vendedor', 'creado_por', 'actualizado_por', 'venta_proyectada_origen', 'empresa')
    # get_readonly_fields, save_model, save_related, actualizar_estatus_cobro ya estaban bien

@admin.register(Pago)
class PagoAdmin(ImportExportModelAdmin): ### MEJORA: Habilitar Import/Export
    list_display = ('numero_documento', 'proveedor', 'empresa','fecha_emision_factura', 'total_factura', 'estatus', 'responsable_pago', 'actualizado_en') ### MEJORA: Quitado vencimiento_inicial por posible ambigüedad
    search_fields = ('numero_documento', 'proveedor__nombre', 'proveedor__identificacion', 'grupo_concepto', 'empresa__razon_social')
    list_filter = ('empresa','estatus', 'tipo_compra', 'pais_proveedor', 'fecha_emision_factura', 'fecha_vencimiento_inicial', 'responsable_pago', 'proveedor') ### MEJORA: Añadido proveedor
    readonly_fields = ('total_factura', 'creado_por', 'creado_en', 'actualizado_por', 'actualizado_en', 'pais_proveedor')
    date_hierarchy = 'fecha_emision_factura' ### MEJORA: Navegación por fecha
    list_select_related = ('proveedor', 'responsable_pago', 'creado_por', 'actualizado_por') ### MEJORA: Optimizar FKs
    fieldsets = (
        (None, {'fields': ('empresa','proveedor', ('fecha_emision_factura', 'numero_documento'), 'grupo_concepto')}),
        ('Detalles Compra/Gasto', {'fields': ('tipo_compra', ('subtotal', 'impuestos', 'total_factura'))}),
        ('Programación Pago', {'fields': (('numero_cuotas', 'fecha_vencimiento_inicial'), 'estatus', 'responsable_pago', 'comentarios', 'adjunto_documento')}),
        ('Auditoría', {'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')), 'classes': ('collapse',)})
    )
    inlines = [DetalleCuotaPagoInline]

    # get_readonly_fields, save_model, save_related, actualizar_estatus_pago ya estaban bien

@admin.register(GastoRecurrente)
class GastoRecurrenteAdmin(ImportExportModelAdmin): ### MEJORA: Habilitar Import/Export
    list_display = ('descripcion', 'grupo_concepto', 'empresa', 'monto_base', 'moneda', 'frecuencia', 'fecha_inicio', 'fecha_fin', 'responsable_pago', 'activo')
    search_fields = ('descripcion', 'grupo_concepto', 'responsable_pago__username', 'empresa__razon_social')
    list_filter = ('empresa','frecuencia', 'activo', 'grupo_concepto', 'moneda', 'responsable_pago')
    readonly_fields = ('creado_por', 'creado_en', 'actualizado_por', 'actualizado_en')
    list_select_related = ('responsable_pago', 'creado_por', 'actualizado_por') ### MEJORA
    fieldsets = (
        (None, {'fields': ('empresa','grupo_concepto', 'descripcion', ('monto_base', 'moneda'))}),
        ('Programación', {'fields': ('frecuencia', 'dia_del_mes', 'fecha_inicio', 'fecha_fin')}),
        ('Gestión', {'fields': ('responsable_pago', 'activo', 'comentarios')}),
        ('Auditoría', {'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')), 'classes': ('collapse',)})
    )
    # save_model ya estaba bien

@admin.register(OcurrenciaGasto)
class OcurrenciaGastoAdmin(ImportExportModelAdmin):
    list_display = ('gasto_recurrente_desc', 'fecha_vencimiento', 'monto', 'estatus', 'fecha_pago_real',
                    'pagado_por_user', # <-- Usamos el método display
                    'antiguedad_vencimiento')
    search_fields = ('gasto_recurrente__descripcion', 'gasto_recurrente__grupo_concepto', 'comentarios')
    list_filter = ('estatus', 'fecha_vencimiento', 'gasto_recurrente__responsable_pago', 'gasto_recurrente')
    readonly_fields = ('creado_en', 'actualizado_en', 'antiguedad_vencimiento', 'gasto_recurrente') # <-- Hacemos gasto_recurrente readonly en el detalle
    # Quitamos 'pagado_por' de list_editable. Si se necesita editar, se hace en el detalle.
    list_editable = ('estatus', 'fecha_pago_real', 'monto')
    date_hierarchy = 'fecha_vencimiento'
    list_select_related = ('gasto_recurrente', 'pagado_por')
    fieldsets = (
        # (None, {'fields': ('gasto_recurrente', ('fecha_vencimiento', 'monto'))}), # Quitado gasto_recurrente porque ahora es readonly
        ('Detalles', {'fields': ('gasto_recurrente', ('fecha_vencimiento', 'monto'))}), # Lo mostramos pero readonly
        ('Estado del Pago', {'fields': ('estatus', 'fecha_pago_real', 'pagado_por', 'comentarios')}),
        ('Auditoría', {'fields': ('creado_en', 'actualizado_en'), 'classes': ('collapse',)}),
    )

    def gasto_recurrente_desc(self, obj):
        return obj.gasto_recurrente.descripcion if obj.gasto_recurrente else '-'
    gasto_recurrente_desc.short_description = 'Gasto Recurrente'
    gasto_recurrente_desc.admin_order_field = 'gasto_recurrente__descripcion'

    def pagado_por_user(self, obj):
        return obj.pagado_por.username if obj.pagado_por else '-'
    pagado_por_user.short_description = 'Pagado Por'
    pagado_por_user.admin_order_field = 'pagado_por__username'


@admin.register(VentaProyectada)
class VentaProyectadaAdmin(ImportExportModelAdmin): # Asegúrate que hereda correctamente
    list_display = ('codigo_oportunidad', 'cliente', 'empresa', 'descripcion_corta',
                    'valor_total_estimado', 'estatus', 'probabilidad_asignada',
                    'valor_ponderado', 'fecha_cierre_estimada',
                    'asesor_comercial',
                    'convertir_a_cobro_link') # <-- Nombre correcto en list_display
    search_fields = ('codigo_oportunidad', 'cliente__nombre', 'descripcion', 'grupo_concepto', 'asesor_comercial__username', 'empresa__razon_social')
    list_filter = ('empresa','estatus', 'fecha_cierre_estimada', 'pais_venta', 'asesor_comercial', 'grupo_concepto', 'cliente')
    readonly_fields = ('margen_estimado', 'probabilidad_asignada', 'valor_ponderado',
                       'creado_por', 'creado_en', 'actualizado_por', 'actualizado_en', 'pais_venta')
    date_hierarchy = 'fecha_cierre_estimada'
    list_select_related = ('cliente', 'asesor_comercial', 'responsable_seguimiento', 'creado_por', 'actualizado_por')
    fieldsets = (
         (None, {'fields': ('empresa','cliente', 'codigo_oportunidad', 'descripcion', 'grupo_concepto', 'estatus')}),
         ('Valores y Cierre', {'fields': ('valor_total_estimado', 'porcentaje_margen', 'margen_estimado', 'probabilidad_asignada', 'valor_ponderado', 'fecha_cierre_estimada')}),
         ('Responsables y Localización', {'fields': ('asesor_comercial', 'responsable_seguimiento', 'pais_venta', 'comentarios')}),
         ('Auditoría', {'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')), 'classes': ('collapse',)})
    )

    # --- ASEGÚRATE QUE ESTOS MÉTODOS ESTÉN DENTRO DE LA CLASE VentaProyectadaAdmin ---
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

    def convertir_a_cobro_link(self, obj): # <-- El nombre debe coincidir exactamente
        if obj.estatus == VentaProyectada.EstatusVenta.GANADA and not obj.cobros_generados.exists():
            url = reverse('gestion:convertir_venta_a_cobro', args=[obj.pk])
            return format_html('<a href="{}" class="button">Convertir a Cobro</a>', url)
        elif obj.cobros_generados.exists():
             cobro = obj.cobros_generados.first()
             # Asegurarse que cobro no sea None antes de acceder a pk
             if cobro:
                 url_cobro = reverse('admin:gestion_cobro_change', args=[cobro.pk])
                 return format_html('<a href="{}">Ver Cobro Creado</a>', url_cobro)
        return "-"
    convertir_a_cobro_link.short_description = 'Acción'

    def save_model(self, request, obj, form, change):
        if not change and not obj.creado_por:
            obj.creado_por = request.user
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)

@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(ImportExportModelAdmin): ### MEJORA: Habilitar Import/Export
    list_display = ('empresa','nombre_banco', 'numero_cuenta', 'moneda', 'saldo_actual', 'actualizado_en', 'actualizado_por_user') ### MEJORA: Nombre usuario
    search_fields = ('nombre_banco', 'numero_cuenta','empresa__razon_social')
    list_filter = ('empresa','moneda', 'nombre_banco')
    readonly_fields = ('creado_por', 'creado_en', 'actualizado_por', 'actualizado_en')
    list_select_related = ('actualizado_por',) ### MEJORA

    def actualizado_por_user(self, obj):
        return obj.actualizado_por.username if obj.actualizado_por else '-'
    actualizado_por_user.short_description = 'Actualizado Por'

    # save_model ya estaba bien

# Opcional: Registrar Contacto directamente con Import/Export
# @admin.register(Contacto)
# class ContactoAdmin(ImportExportModelAdmin):
#     list_display = ('nombre', 'cargo', 'email', 'cliente', 'proveedor', 'es_principal')
#     list_filter = ('es_principal', 'cliente', 'proveedor') ### MEJORA: Orden filtro
#     search_fields = ('nombre', 'email', 'cargo', 'cliente__nombre', 'proveedor__nombre') ### MEJORA: Buscar por cargo
#     list_select_related = ('cliente', 'proveedor') ### MEJORA