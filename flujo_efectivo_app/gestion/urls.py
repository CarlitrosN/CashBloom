# gestion/urls.py
from django.urls import path
from . import views # Importar las vistas

app_name = 'gestion' # Namespace

urlpatterns = [
    # URLs principales y reportes
    path('', views.dashboard_view, name='dashboard'), # Dashboard como raíz de /gestion/
    path('flujo-efectivo/', views.flujo_efectivo_report_view, name='flujo_efectivo_report'),
    path('simulacion-flujo/', views.simulacion_flujo_view, name='simulacion_flujo'),
    path('pipeline/', views.pipeline_view, name='pipeline_ventas'),
    path('venta-proyectada/<int:venta_id>/convertir-a-cobro/', views.convertir_a_cobro_view, name='convertir_venta_a_cobro'),

    # URLs CRUD para Cobros
    path('cobros/', views.CobroListView.as_view(), name='cobro_list'), # <-- La que causa el error si falta/está mal
    path('cobros/<int:pk>/', views.CobroDetailView.as_view(), name='cobro_detail'),
    path('cobros/nuevo/', views.CobroCreateView.as_view(), name='cobro_create'),
    path('cobros/<int:pk>/editar/', views.CobroUpdateView.as_view(), name='cobro_update'),
    path('cobros/<int:pk>/eliminar/', views.CobroDeleteView.as_view(), name='cobro_delete'),

    # --- URLs CRUD para Pagos ---
    path('pagos/', views.PagoListView.as_view(), name='pago_list'),
    path('pagos/<int:pk>/', views.PagoDetailView.as_view(), name='pago_detail'),
    path('pagos/nuevo/', views.PagoCreateView.as_view(), name='pago_create'),
    path('pagos/<int:pk>/editar/', views.PagoUpdateView.as_view(), name='pago_update'),
    path('pagos/<int:pk>/eliminar/', views.PagoDeleteView.as_view(), name='pago_delete'),

    # --- URLs CRUD para Clientes ---
    path('clientes/', views.ClienteListView.as_view(), name='cliente_list'),
    path('clientes/<int:pk>/', views.ClienteDetailView.as_view(), name='cliente_detail'),
    path('clientes/nuevo/', views.ClienteCreateView.as_view(), name='cliente_create'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_update'),
    path('clientes/<int:pk>/eliminar/', views.ClienteDeleteView.as_view(), name='cliente_delete'),

    # --- URLs CRUD para Proveedores ---
    path('proveedores/', views.ProveedorListView.as_view(), name='proveedor_list'), # Crear estas vistas
    path('proveedores/<int:pk>/', views.ProveedorDetailView.as_view(), name='proveedor_detail'), # Crear estas vistas
    path('proveedores/nuevo/', views.ProveedorCreateView.as_view(), name='proveedor_create'), # Crear estas vistas
    path('proveedores/<int:pk>/editar/', views.ProveedorUpdateView.as_view(), name='proveedor_update'), # Crear estas vistas
    path('proveedores/<int:pk>/eliminar/', views.ProveedorDeleteView.as_view(), name='proveedor_delete'), # Crear
   
 # --- URLs CRUD para Cuentas Bancarias ---
    path('cuentas-bancarias/', views.CuentaBancariaListView.as_view(), name='cuenta_bancaria_list'),
    # path('cuentas-bancarias/<int:pk>/', views.CuentaBancariaDetailView.as_view(), name='cuenta_bancaria_detail'), # Si se crea DetailView
    path('cuentas-bancarias/nueva/', views.CuentaBancariaCreateView.as_view(), name='cuenta_bancaria_create'),
    path('cuentas-bancarias/<int:pk>/editar/', views.CuentaBancariaUpdateView.as_view(), name='cuenta_bancaria_update'),
    path('cuentas-bancarias/<int:pk>/eliminar/', views.CuentaBancariaDeleteView.as_view(), name='cuenta_bancaria_delete'),
 
 # --- URLs CRUD para Gastos Recurrentes (Plantillas) ---
    path('gastos-recurrentes/', views.GastoRecurrenteListView.as_view(), name='gasto_recurrente_list'),
    path('gastos-recurrentes/<int:pk>/', views.GastoRecurrenteDetailView.as_view(), name='gasto_recurrente_detail'),
    path('gastos-recurrentes/nuevo/', views.GastoRecurrenteCreateView.as_view(), name='gasto_recurrente_create'),
    path('gastos-recurrentes/<int:pk>/editar/', views.GastoRecurrenteUpdateView.as_view(), name='gasto_recurrente_update'),
    path('gastos-recurrentes/<int:pk>/eliminar/', views.GastoRecurrenteDeleteView.as_view(), name='gasto_recurrente_delete'),

# --- URLs CRUD/Gestión para Ocurrencias de Gasto ---
    path('ocurrencias-gasto/', views.OcurrenciaGastoListView.as_view(), name='ocurrencia_gasto_list'),
    path('ocurrencias-gasto/<int:pk>/editar/', views.OcurrenciaGastoUpdateView.as_view(), name='ocurrencia_gasto_update'),
    # No incluimos _create ni _delete por defecto   

# --- URLs CRUD para Ventas Proyectadas ---
    path('ventas-proyectadas/', views.VentaProyectadaListView.as_view(), name='venta_proyectada_list'),
    path('ventas-proyectadas/<int:pk>/', views.VentaProyectadaDetailView.as_view(), name='venta_proyectada_detail'),
    path('ventas-proyectadas/nueva/', views.VentaProyectadaCreateView.as_view(), name='venta_proyectada_create'),
    path('ventas-proyectadas/<int:pk>/editar/', views.VentaProyectadaUpdateView.as_view(), name='venta_proyectada_update'),
    path('ventas-proyectadas/<int:pk>/eliminar/', views.VentaProyectadaDeleteView.as_view(), name='venta_proyectada_delete'),

# --- URLs Listas Detalladas de Cuotas ---
    path('cuotas-cobrar/', views.DetalleCuotaCobroListView.as_view(), name='detallecuotacobro_list'),
    path('cuotas-pagar/', views.DetalleCuotaPagoListView.as_view(), name='detallecuotapago_list'),

# --- URLs Reportes Financieros --- 

    path('reportes/aging-cobrar/', views.AgingReportView.as_view(), name='aging_report_cobrar')
    # TODO: Añadir URLs para CRUD Faltantes.
]