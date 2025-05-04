# gestion/forms.py
from django import forms
from decimal import Decimal, InvalidOperation
from django.contrib.auth import get_user_model
from taggit.forms import TagWidget # Para widget de tags
from django.core.exceptions import ValidationError

# --- Importar modelos locales ---
from .models import (
    Cliente, Proveedor, Contacto, # Modelos de Terceros
    Cobro, DetalleCuotaCobro,     # Modelos de Cobranza
    Pago, DetalleCuotaPago,       # Modelos de Pagos
    VentaProyectada, CuentaBancaria, GastoRecurrente, OcurrenciaGasto   # Otros modelos relevantes
)

# --- Obtener el modelo User activo ---
User = get_user_model()

# --- Clases CSS Base para Tailwind ---
base_input_classes = 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:border-indigo-500 focus:ring focus:ring-indigo-500 focus:ring-opacity-50 text-sm disabled:bg-gray-100 disabled:cursor-not-allowed'
base_select_classes = f'{base_input_classes} pr-10'
base_textarea_classes = base_input_classes
base_file_classes = 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 mt-1 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500'
inline_input_classes = 'block w-full border-gray-300 rounded-md shadow-sm focus:border-indigo-500 focus:ring focus:ring-indigo-500 focus:ring-opacity-50 text-xs py-1 px-2 disabled:bg-gray-100 disabled:cursor-not-allowed'
inline_select_classes = f'{inline_input_classes} pr-8'
inline_textarea_classes = inline_input_classes
checkbox_classes = 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'

# --- Función Helper para Aplicar Clases ---
def apply_tailwind_classes(form_fields):
    """Aplica clases CSS de Tailwind a los widgets de un diccionario de campos."""
    for field_name, field in form_fields.items():
         widget = field.widget
         current_attrs = widget.attrs
         current_class = current_attrs.get('class', '')
         target_class = ''
         # Detectar si el widget ya tiene una clase específica de inline (más robusto que solo 'inline')
         is_inline = any(cls in current_class for cls in ['form-input-inline', 'form-select-inline', 'form-textarea-inline'])

         # Determinar clases base según tipo de widget
         if isinstance(widget, forms.CheckboxInput):
             target_class = checkbox_classes
         elif isinstance(widget, forms.Select):
             target_class = inline_select_classes if is_inline else base_select_classes
         elif isinstance(widget, forms.Textarea):
             target_class = inline_textarea_classes if is_inline else base_textarea_classes
         elif isinstance(widget, forms.ClearableFileInput) or isinstance(widget, forms.FileInput):
             target_class = base_file_classes
         elif isinstance(widget, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.PasswordInput, forms.URLInput, forms.DateInput, forms.DateTimeInput, forms.TimeInput)):
             target_class = inline_input_classes if is_inline else base_input_classes
         # No aplicar a radios o widgets especiales como TagWidget por defecto
         elif not isinstance(widget, (forms.RadioSelect, TagWidget)):
             target_class = inline_input_classes if is_inline else base_input_classes

         # Combinar clases existentes y nuevas
         if target_class:
             existing_classes = set(current_class.split())
             new_classes = set(target_class.split())
             # Añadir solo las clases base que no estén ya (evita duplicados)
             final_classes = existing_classes.union(new_classes - existing_classes)
             widget.attrs['class'] = ' '.join(sorted(list(final_classes)))


# ============================================
# === Formulario Cliente =====================
# ============================================
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['identificacion', 'nombre', 'telefono', 'email', 'direccion', 'pais', 'tags']
        widgets = {
            'tags': TagWidget(attrs={'placeholder': 'Etiquetas separadas por comas'}),
            'direccion': forms.Textarea(attrs={'rows': 3}),
            'identificacion': forms.TextInput(attrs={'placeholder': 'NIT, RUT, CUIT, etc.'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre o Razón Social'}),
            'email': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Número telefónico'}),
            'pais': forms.TextInput(attrs={'placeholder': 'País de residencia'}),
        }
        labels = {
            'identificacion': 'Identificación (*)', 'nombre': 'Nombre / Razón Social (*)',
            'tags': 'Etiquetas / Categorías', 'email': 'Correo Electrónico',
            'direccion': 'Dirección Completa'
        }

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None)
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)


# ============================================
# === Formulario Proveedor ===================
# ============================================
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['identificacion', 'nombre', 'telefono', 'email', 'direccion', 'pais', 'tags']
        widgets = {
            'tags': TagWidget(attrs={'placeholder': 'Etiquetas separadas por comas'}),
            'direccion': forms.Textarea(attrs={'rows': 3}),
            'identificacion': forms.TextInput(attrs={'placeholder': 'NIT, RUT, CUIT, etc.'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre o Razón Social'}),
            'email': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Número telefónico'}),
            'pais': forms.TextInput(attrs={'placeholder': 'País de origen'}),
        }
        labels = {
            'identificacion': 'Identificación (*)', 'nombre': 'Nombre / Razón Social (*)',
            'tags': 'Etiquetas / Categorías', 'email': 'Correo Electrónico',
            'direccion': 'Dirección Completa'
        }

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None)
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)


# ============================================
# === Formulario Inline para Contacto ========
# ============================================
class ContactoForm(forms.ModelForm):
    """Formulario para usar en inline formsets de Contacto."""
    nombre = forms.CharField(label="Nombre", widget=forms.TextInput(attrs={'placeholder':'Nombre Contacto', 'class':'form-input-inline'}))
    cargo = forms.CharField(label="Cargo", required=False, widget=forms.TextInput(attrs={'placeholder':'Cargo', 'class':'form-input-inline'}))
    email = forms.EmailField(label="Email", required=False, widget=forms.EmailInput(attrs={'placeholder':'email@contacto.com', 'class':'form-input-inline'}))
    telefono_directo = forms.CharField(label="Tel. Directo", max_length=50, required=False, widget=forms.TextInput(attrs={'placeholder': 'Fijo/Directo', 'class':'form-input-inline'}))
    celular = forms.CharField(label="Celular", max_length=50, required=False, widget=forms.TextInput(attrs={'placeholder': 'Móvil', 'class':'form-input-inline'}))
    es_principal = forms.BooleanField(label="Principal?", required=False, widget=forms.CheckboxInput(attrs={'class':checkbox_classes})) # Usar clase definida
    observaciones = forms.CharField(label="Obs.", widget=forms.Textarea(attrs={'rows': 1, 'class':'form-textarea-inline'}), required=False)

    class Meta:
        model = Contacto
        fields = ['nombre', 'cargo', 'email', 'telefono_directo', 'celular', 'es_principal', 'observaciones']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)


# ============================================
# === Formulario Principal para Cobro ========
# ============================================
class CobroForm(forms.ModelForm):
    """Formulario para Crear y Actualizar Cobros."""
    cliente = forms.ModelChoiceField(queryset=Cliente.objects.none(), label="Cliente (*)") # Queryset se filtra en init
    vendedor = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Vendedor", required=False)
    responsable_seguimiento = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Responsable Seguimiento", required=False)
    venta_proyectada_origen = forms.ModelChoiceField(queryset=VentaProyectada.objects.none(), label="Venta Proyectada Origen", required=False) # Queryset se filtra en init
    fecha_factura = forms.DateField(label="Fecha Documento (*)", widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fecha_vencimiento_inicial = forms.DateField(label="Vencimiento Inicial", required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    subtotal = forms.DecimalField(label="Subtotal (*)", max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))
    impuestos = forms.DecimalField(label="Impuestos", max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'), widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))
    numero_cuotas = forms.IntegerField(min_value=1, max_value=12, initial=1, label="Número de Cuotas (*)", help_text="Máx. 12. Las cuotas se generan al crear.", widget=forms.NumberInput(attrs={'min': '1', 'max': '12'}))
    comentarios = forms.CharField(label="Comentarios / Observaciones", widget=forms.Textarea(attrs={'rows': 3}), required=False)
    adjunto_factura = forms.FileField(label="Adjuntar Factura (PDF, IMG)", required=False, widget=forms.ClearableFileInput())
    grupo_concepto = forms.CharField(label="Grupo / Concepto", max_length=150, required=False)
    pais_cobro = forms.CharField(label="País Cobro", max_length=100, required=False)
    numero_documento = forms.CharField(label="Nº Documento (*)", max_length=100)
    producto_vendido_desc = forms.CharField(label="Descripción Productos/Servicios", widget=forms.Textarea(attrs={'rows': 3}), required=False)
    tipo_venta = forms.ChoiceField(label="Tipo de Venta", choices=Cobro.TipoVenta.choices)
    # Campo Moneda añadido
    moneda = forms.CharField(label="Moneda Transacción (*)", max_length=3, initial='USD', widget=forms.TextInput(attrs={'placeholder':'Ej: USD, EUR'}))

    class Meta:
        model = Cobro
        fields = [
            'cliente', 'venta_proyectada_origen', 'grupo_concepto', 'pais_cobro',
            'fecha_factura', 'numero_documento', 'producto_vendido_desc', 'tipo_venta',
            'vendedor', 'subtotal', 'impuestos', 'numero_cuotas', 'moneda', # Moneda añadida
            'fecha_vencimiento_inicial', 'responsable_seguimiento', 'comentarios',
            'adjunto_factura',
        ]

    def __init__(self, *args, **kwargs):
         empresa_id = kwargs.pop('empresa_id', None) # Recibir empresa_id
         super().__init__(*args, **kwargs)
         apply_tailwind_classes(self.fields) # Aplicar estilos
         # Filtrar querysets
         if empresa_id:
             try:
                 self.fields['cliente'].queryset = Cliente.objects.filter(empresa_id=empresa_id).order_by('nombre')
                 self.fields['venta_proyectada_origen'].queryset = VentaProyectada.objects.filter(empresa_id=empresa_id, estatus='GANA').order_by('-fecha_cierre_estimada')
                 # Filtrar usuarios si es necesario (requiere lógica de UsuarioEmpresa)
                 # users_empresa = User.objects.filter(empresas_asignadas__empresa_id=empresa_id, is_active=True).distinct()
                 # self.fields['vendedor'].queryset = users_empresa.order_by('username')
                 # self.fields['responsable_seguimiento'].queryset = users_empresa.order_by('username')
             except Exception as e:
                  logger = logging.getLogger(__name__)
                  logger.error(f"Error filtrando QSet en CobroForm para empresa {empresa_id}: {e}")
                  self.fields['cliente'].queryset = Cliente.objects.none()
                  self.fields['venta_proyectada_origen'].queryset = VentaProyectada.objects.none()
         else:
             # Si no hay empresa_id, dejar querysets vacíos para seguridad
             self.fields['cliente'].queryset = Cliente.objects.none()
             self.fields['venta_proyectada_origen'].queryset = VentaProyectada.objects.none()

         # Lógica readonly para numero_cuotas en edición
         if self.instance and self.instance.pk:
             if 'numero_cuotas' in self.fields:
                self.fields['numero_cuotas'].widget.attrs['readonly'] = True
                self.fields['numero_cuotas'].widget.attrs['class'] += ' bg-gray-100 cursor-not-allowed'
                self.fields['numero_cuotas'].help_text = "No editable una vez creado el cobro."


# ============================================
# === Formulario Inline para DetalleCuotaCobro ===
# ============================================
class DetalleCuotaCobroForm(forms.ModelForm):
    """Formulario para editar campos específicos de una cuota en un inline formset."""
    monto_cuota = forms.DecimalField(label="Monto Bruto", disabled=True, widget=forms.NumberInput(attrs={'class':'form-input-inline text-right'}))
    fecha_vencimiento = forms.DateField(label="Vencimiento", disabled=True, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'text', 'class': 'form-input-inline'}))
    estatus = forms.ChoiceField(choices=DetalleCuotaCobro.EstatusCuota.choices, widget=forms.Select(attrs={'class': 'form-select-inline'}))
    fecha_pago_real = forms.DateField(required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-input-inline'}))
    cuenta_bancaria_deposito = forms.ModelChoiceField(queryset=CuentaBancaria.objects.none(), required=False, label="Cta. Depósito", widget=forms.Select(attrs={'class':'form-select-inline'})) # Filtrar en init
    numero_retencion = forms.CharField(label="Nº Ret.", max_length=100, required=False, widget=forms.TextInput(attrs={'class':'form-input-inline'}))
    valor_retencion = forms.DecimalField(label="Val. Ret.", max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'), widget=forms.NumberInput(attrs={'step': '0.01', 'class':'form-input-inline text-right'}))
    observaciones_cuota = forms.CharField(label="Obs.", widget=forms.Textarea(attrs={'rows': 1, 'class': 'form-textarea-inline'}), required=False)

    class Meta:
        model = DetalleCuotaCobro
        fields = ['monto_cuota', 'fecha_vencimiento', 'estatus', 'fecha_pago_real', 'cuenta_bancaria_deposito', 'numero_retencion', 'valor_retencion', 'observaciones_cuota']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)
        # Aplicar estilos a disabled
        if self.fields['monto_cuota'].disabled: self.fields['monto_cuota'].widget.attrs['class'] += ' bg-gray-100 cursor-not-allowed'
        if self.fields['fecha_vencimiento'].disabled: self.fields['fecha_vencimiento'].widget.attrs['class'] += ' bg-gray-100 cursor-not-allowed'; self.fields['fecha_vencimiento'].widget.input_type = 'text'

        # Filtrar cuenta bancaria por la empresa del cobro padre (si existe)
        if self.instance and hasattr(self.instance, 'cobro') and self.instance.cobro and hasattr(self.instance.cobro, 'empresa') and self.instance.cobro.empresa:
            empresa_id = self.instance.cobro.empresa.id
            self.fields['cuenta_bancaria_deposito'].queryset = CuentaBancaria.objects.filter(empresa_id=empresa_id).order_by('nombre_banco', 'numero_cuenta')
        else:
             # Si no se puede determinar la empresa (ej: creando), dejar vacío o mostrar todas?
             # Es mejor asegurarse que la vista pase la info o filtrar basado en el padre.
             # Como este form se usa en INLINE, self.instance.cobro debería existir al editar.
             self.fields['cuenta_bancaria_deposito'].queryset = CuentaBancaria.objects.none()


# ============================================
# === Formulario Principal para Pago =========
# ============================================
class PagoForm(forms.ModelForm):
    """Formulario para Crear y Actualizar Pagos a Proveedores."""
    proveedor = forms.ModelChoiceField(queryset=Proveedor.objects.none(), label="Proveedor (*)") # Filtrar en init
    responsable_pago = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Responsable de Pago", required=False)
    fecha_emision_factura = forms.DateField(label="Fecha Emisión Fact. Prov. (*)", widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fecha_vencimiento_inicial = forms.DateField(label="Vencimiento Inicial/Único", required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    subtotal = forms.DecimalField(label="Subtotal (*)", max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))
    impuestos = forms.DecimalField(label="Impuestos", max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'), widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))
    numero_cuotas = forms.IntegerField(min_value=1, max_value=12, initial=1, label="Número de Cuotas (*)", help_text="Máx. 12. Las cuotas se generan al crear.", widget=forms.NumberInput(attrs={'min': '1', 'max': '12'}))
    comentarios = forms.CharField(label="Comentarios / Observaciones", widget=forms.Textarea(attrs={'rows': 3}), required=False)
    adjunto_documento = forms.FileField(label="Adjuntar Factura Prov. (PDF, IMG)", required=False, widget=forms.ClearableFileInput())
    grupo_concepto = forms.CharField(label="Grupo / Concepto Pago", max_length=150, required=False)
    numero_documento = forms.CharField(label="Nº Factura Proveedor (*)", max_length=100)
    tipo_compra = forms.ChoiceField(label="Tipo de Compra/Gasto", choices=Pago.TipoCompra.choices)
    # Campo Moneda añadido
    moneda = forms.CharField(label="Moneda Transacción (*)", max_length=3, initial='USD', widget=forms.TextInput(attrs={'placeholder':'Ej: USD, EUR'}))

    class Meta:
        model = Pago
        fields = ['proveedor', 'grupo_concepto', 'fecha_emision_factura', 'numero_documento', 'tipo_compra', 'subtotal', 'impuestos', 'numero_cuotas', 'moneda', 'fecha_vencimiento_inicial', 'responsable_pago', 'comentarios', 'adjunto_documento']

    def __init__(self, *args, **kwargs):
         empresa_id = kwargs.pop('empresa_id', None) # Recibir empresa_id
         super().__init__(*args, **kwargs)
         apply_tailwind_classes(self.fields)
         # Filtrar querysets
         if empresa_id:
             try:
                 self.fields['proveedor'].queryset = Proveedor.objects.filter(empresa_id=empresa_id).order_by('nombre')
                 # Filtrar responsable_pago si es necesario
                 # users_empresa = User.objects.filter(empresas_asignadas__empresa_id=empresa_id, is_active=True).distinct()
                 # self.fields['responsable_pago'].queryset = users_empresa.order_by('username')
             except Exception as e:
                  logger = logging.getLogger(__name__)
                  logger.error(f"Error filtrando QSet en PagoForm para empresa {empresa_id}: {e}")
                  self.fields['proveedor'].queryset = Proveedor.objects.none()
         else:
             self.fields['proveedor'].queryset = Proveedor.objects.none()

         # Lógica readonly para numero_cuotas
         if self.instance and self.instance.pk:
             if 'numero_cuotas' in self.fields:
                self.fields['numero_cuotas'].widget.attrs['readonly'] = True
                self.fields['numero_cuotas'].widget.attrs['class'] += ' bg-gray-100 cursor-not-allowed'
                self.fields['numero_cuotas'].help_text = "No editable una vez creado el pago."

# ============================================
# === Formulario Inline para DetalleCuotaPago ===
# ============================================
class DetalleCuotaPagoForm(forms.ModelForm):
    """Formulario para editar campos específicos de una cuota de pago."""
    monto_cuota = forms.DecimalField(label="Monto", max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'class':'form-input-inline text-right'}))
    fecha_vencimiento = forms.DateField(label="Vencim.", widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-input-inline'}))
    estatus = forms.ChoiceField(choices=DetalleCuotaPago.EstatusCuotaPago.choices, widget=forms.Select(attrs={'class': 'form-select-inline'}))
    fecha_pago_real = forms.DateField(required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-input-inline'}))
    observaciones_cuota = forms.CharField(label="Obs.", widget=forms.Textarea(attrs={'rows': 1, 'class': 'form-textarea-inline'}), required=False)

    class Meta:
        model = DetalleCuotaPago
        fields = ['monto_cuota', 'fecha_vencimiento', 'estatus', 'fecha_pago_real', 'observaciones_cuota']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)

# ============================================
# === Formulario Cuenta Bancaria ===========
# ============================================
class CuentaBancariaForm(forms.ModelForm):
    """Formulario para Crear y Actualizar Cuentas Bancarias."""
    nombre_banco = forms.CharField(label="Nombre del Banco (*)", max_length=150)
    numero_cuenta = forms.CharField(label="Número de Cuenta / Alias (*)", max_length=100)
    moneda = forms.CharField(label="Moneda (*)", max_length=3, initial='USD', widget=forms.TextInput(attrs={'placeholder':'Ej: USD, EUR'})) # Max length 3
    saldo_actual = forms.DecimalField(label="Saldo Actual (*)", max_digits=18, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))

    class Meta:
        model = CuentaBancaria
        # El campo 'empresa' se asigna en la vista, no aquí
        fields = ['nombre_banco', 'numero_cuenta', 'moneda', 'saldo_actual']

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None)
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)

# ============================================
# === Formulario Gasto Recurrente ==========
# ============================================
class GastoRecurrenteForm(forms.ModelForm):
    """Formulario para Crear y Actualizar Plantillas de Gastos Recurrentes."""
    grupo_concepto = forms.CharField(label="Grupo / Concepto (*)", max_length=150, widget=forms.TextInput(attrs={'placeholder':'Ej: Alquiler, Nómina, Software...'}))
    descripcion = forms.CharField(label="Descripción Detallada (*)", widget=forms.Textarea(attrs={'rows': 3, 'placeholder':'Descripción específica del gasto recurrente'}))
    monto_base = forms.DecimalField(label="Monto Base (*)", max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))
    moneda = forms.CharField(label="Moneda (*)", max_length=3, initial='USD', widget=forms.TextInput(attrs={'placeholder': 'Ej: USD, EUR'})) # Max length 3
    frecuencia = forms.ChoiceField(label="Frecuencia (*)", choices=GastoRecurrente.FrecuenciaGasto.choices)
    dia_del_mes = forms.IntegerField(label="Día del Mes (si aplica)", required=False, min_value=1, max_value=31, help_text="Para freq. mensual, bimestral, etc.", widget=forms.NumberInput(attrs={'min': '1', 'max':'31'}))
    fecha_inicio = forms.DateField(label="Fecha Inicio (Primer Pago) (*)", widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    fecha_fin = forms.DateField(label="Fecha Final (Opcional)", required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    responsable_pago = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Responsable de Pago", required=False)
    activo = forms.BooleanField(label="¿Plantilla Activa?", required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': checkbox_classes}))
    comentarios = forms.CharField(label="Comentarios / Observaciones", widget=forms.Textarea(attrs={'rows': 2}), required=False)

    class Meta:
        model = GastoRecurrente
        # El campo 'empresa' se asigna en la vista
        fields = ['grupo_concepto', 'descripcion', 'monto_base', 'moneda', 'frecuencia', 'dia_del_mes', 'fecha_inicio', 'fecha_fin', 'responsable_pago', 'activo', 'comentarios']

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None) # Recibir empresa_id
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)
        # Filtrar usuarios si es necesario
        # if empresa_id:
        #     users_empresa = User.objects.filter(empresas_asignadas__empresa_id=empresa_id, is_active=True).distinct()
        #     self.fields['responsable_pago'].queryset = users_empresa.order_by('username')

    def clean_dia_del_mes(self):
        data = self.cleaned_data; frecuencia = data.get('frecuencia'); dia_mes = data.get('dia_del_mes')
        frecuencias_con_dia = [GastoRecurrente.FrecuenciaGasto.MENSUAL, GastoRecurrente.FrecuenciaGasto.BIMESTRAL, GastoRecurrente.FrecuenciaGasto.TRIMESTRAL, GastoRecurrente.FrecuenciaGasto.SEMESTRAL, GastoRecurrente.FrecuenciaGasto.ANUAL]
        if frecuencia not in frecuencias_con_dia and dia_mes is not None: raise ValidationError("El 'Día del Mes' solo aplica para frecuencias mensuales o mayores.")
        if frecuencia in frecuencias_con_dia and dia_mes is None: raise ValidationError("Debe especificar el 'Día del Mes' para la frecuencia seleccionada.")
        return dia_mes

    def clean(self):
        cleaned_data = super().clean(); fecha_inicio = cleaned_data.get("fecha_inicio"); fecha_fin = cleaned_data.get("fecha_fin")
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio: self.add_error('fecha_fin', "La fecha final no puede ser anterior a la fecha de inicio.")
        return cleaned_data

# ============================================
# === Formulario Ocurrencia Gasto (Edición) ==
# ============================================
class OcurrenciaGastoForm(forms.ModelForm):
    """Formulario para Editar detalles de una Ocurrencia de Gasto."""
    estatus = forms.ChoiceField(label="Estado (*)", choices=OcurrenciaGasto.EstatusOcurrencia.choices)
    fecha_pago_real = forms.DateField(label="Fecha Real de Pago", required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    monto = forms.DecimalField(label="Monto Pagado (*)", max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01'}))
    pagado_por = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Pagado Por", required=False)
    comentarios = forms.CharField(label="Comentarios/Ref. Pago", widget=forms.Textarea(attrs={'rows': 2}), required=False)

    class Meta:
        model = OcurrenciaGasto
        fields = ['estatus', 'fecha_pago_real', 'monto', 'pagado_por', 'comentarios']

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None) # Recibir empresa_id
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)
        # Filtrar usuarios si es necesario
        # if empresa_id:
        #     users_empresa = User.objects.filter(empresas_asignadas__empresa_id=empresa_id, is_active=True).distinct()
        #     self.fields['pagado_por'].queryset = users_empresa.order_by('username')

    def clean(self):
        cleaned_data = super().clean(); estatus = cleaned_data.get("estatus"); fecha_pago_real = cleaned_data.get("fecha_pago_real")
        if estatus == OcurrenciaGasto.EstatusOcurrencia.PAGADO and not fecha_pago_real: self.add_error('fecha_pago_real', "La fecha de pago es obligatoria si el estado es 'Pagado'.")
        return cleaned_data

# ============================================
# === Formulario Venta Proyectada ==========
# ============================================
class VentaProyectadaForm(forms.ModelForm):
    """Formulario para Crear y Actualizar Ventas Proyectadas."""
    cliente = forms.ModelChoiceField(queryset=Cliente.objects.none(), label="Cliente Potencial", required=False) # Filtrar en init
    asesor_comercial = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Asesor Comercial", required=False)
    responsable_seguimiento = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('username'), label="Responsable Seguimiento", required=False)
    grupo_concepto = forms.CharField(label="Grupo / Concepto Venta", max_length=150, required=False, widget=forms.TextInput(attrs={'placeholder':'Ej: Licencia Software, Consultoría'}))
    codigo_oportunidad = forms.CharField(label="Código Oportunidad", max_length=50, required=False)
    estatus = forms.ChoiceField(label="Estatus (*)", choices=VentaProyectada.EstatusVenta.choices)
    pais_venta = forms.CharField(label="País Venta", max_length=100, required=False)
    descripcion = forms.CharField(label="Descripción Venta", widget=forms.Textarea(attrs={'rows': 3}), required=False)
    valor_total_estimado = forms.DecimalField(label="Valor Total Estimado (*)", max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'step':'0.01', 'placeholder':'0.00'}))
    porcentaje_margen = forms.DecimalField(label="% Margen Estimado", max_digits=5, decimal_places=2, min_value=0, max_value=100, widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}))
    fecha_cierre_estimada = forms.DateField(label="Fecha Estimada Cierre (*)", widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    comentarios = forms.CharField(label="Comentarios / Observaciones", widget=forms.Textarea(attrs={'rows': 2}), required=False)
    # Campo Moneda añadido
    moneda = forms.CharField(label="Moneda (*)", max_length=3, initial='USD', widget=forms.TextInput(attrs={'placeholder':'Ej: USD, EUR'}))

    class Meta:
        model = VentaProyectada
        fields = ['cliente', 'asesor_comercial', 'responsable_seguimiento', 'grupo_concepto', 'codigo_oportunidad', 'estatus', 'pais_venta', 'descripcion', 'valor_total_estimado', 'porcentaje_margen', 'moneda', 'fecha_cierre_estimada', 'comentarios']

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None) # Recibir empresa_id
        super().__init__(*args, **kwargs)
        apply_tailwind_classes(self.fields)
        # Filtrar querysets
        if empresa_id:
            try:
                self.fields['cliente'].queryset = Cliente.objects.filter(empresa_id=empresa_id).order_by('nombre')
                # Filtrar usuarios si es necesario
                # users_empresa = User.objects.filter(empresas_asignadas__empresa_id=empresa_id, is_active=True).distinct()
                # self.fields['asesor_comercial'].queryset = users_empresa.order_by('username')
                # self.fields['responsable_seguimiento'].queryset = users_empresa.order_by('username')
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error filtrando QSet en VentaProyectadaForm para empresa {empresa_id}: {e}")
                self.fields['cliente'].queryset = Cliente.objects.none()
        else:
            self.fields['cliente'].queryset = Cliente.objects.none()