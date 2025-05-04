# core/admin.py
from django.contrib import admin
from .models import Empresa, UsuarioEmpresa, Plan, SuscripcionEmpresa
from django.utils.safestring import mark_safe

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    # --- Mostrar logo en la lista (opcional pero útil) ---
    def logo_preview(self, obj):
        if obj.logo:
            # Crear una pequeña vista previa del logo
            return mark_safe(f'<img src="{obj.logo.url}" style="max-height: 50px; max-width: 100px;" />')
        return "(Sin logo)"
    logo_preview.short_description = 'Logo Preview'

    list_display = ('razon_social', 'identificacion', 'pais', 'moneda', 'logo_preview', 'actualizado_en') # Añadido logo_preview
    search_fields = ('razon_social', 'identificacion')
    list_filter = ('pais','moneda') # Quitado creado_en ya que no es tan relevante para una única empresa
    readonly_fields = ('creado_en', 'actualizado_en', 'creado_por', 'actualizado_por', 'logo_preview') # Añadido logo_preview a readonly

    # --- Organizar campos en el formulario de edición ---
    fieldsets = (
        (None, {
            'fields': ('identificacion', 'razon_social', 'telefono', 'pais', 'moneda')
        }),
        ('Logotipo', { # Nueva sección para el logo
            'fields': ('logo', 'logo_preview'), # Mostrar campo de carga y preview
        }),
        ('Auditoría', {
            'fields': (('creado_por', 'creado_en'), ('actualizado_por', 'actualizado_en')),
            'classes': ('collapse',) # Ocultar por defecto
        }),
    )

    def save_model(self, request, obj, form, change):
        # La lógica del singleton ya está en el modelo, pero mantenemos la auditoría
        if not change and not obj.creado_por:
            obj.creado_por = request.user
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)

@admin.register(UsuarioEmpresa)
class UsuarioEmpresaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa') # Añadir 'rol' si se implementa
    list_filter = ('empresa', 'usuario') # Añadir 'rol' si se implementa
    search_fields = ('usuario__username', 'empresa__razon_social')
    autocomplete_fields = ['usuario', 'empresa'] # Facilita la selección
    list_per_page = 20
    
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        'slug',
        'nombre',
        'limite_empresas',
        'limite_usuarios',
        'permite_aging_report',
        'permite_alertas',
        'activo',
    )
    list_filter = ('activo',)
    search_fields = ('slug', 'nombre', 'descripcion')
    # Para hacer estos campos editables en la lista:
    # list_editable = ('permite_aging_report', 'permite_alertas', 'activo')
    # Para autogenerar slug desde nombre (siempre que nombre sea único y limpio):
    # prepopulated_fields = {'slug': ('nombre',)}


@admin.register(SuscripcionEmpresa)
class SuscripcionEmpresaAdmin(admin.ModelAdmin):
    list_display = (
        'empresa',
        'plan',
        'fecha_inicio',
        'fecha_fin',
        'activa',
        'is_valid_display',
    )
    list_filter = ('plan', 'activa', 'fecha_inicio', 'fecha_fin')
    search_fields = ('empresa__razon_social', 'plan__nombre')
    autocomplete_fields = ['empresa', 'plan']
    list_select_related = ('empresa', 'plan')
    readonly_fields = ('is_valid_display',)
    date_hierarchy = 'fecha_inicio'

    def is_valid_display(self, obj):
        """Icono que indica si la suscripción está vigente."""
        return obj.is_valid()
    is_valid_display.boolean = True
    is_valid_display.short_description = "Vigente?"