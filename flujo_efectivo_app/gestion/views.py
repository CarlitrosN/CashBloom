# gestion/views.py
import logging
import json
from datetime import timedelta, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from collections import OrderedDict, defaultdict
from io import BytesIO
import csv

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q, F
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required # Keep for function views
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import HttpResponse
from reportlab.pdfgen import canvas
import math

# --- Importar modelos locales ---
from core.models import Empresa # Importar Empresa desde core
from .models import (
    CuentaBancaria, DetalleCuotaCobro, DetalleCuotaPago,
    OcurrenciaGasto, VentaProyectada, Cobro, Pago, GastoRecurrente, Cliente, Proveedor, Contacto
)
# --- Importar formularios ---
from .forms import (
    CobroForm, DetalleCuotaCobroForm, PagoForm, DetalleCuotaPagoForm,
    ClienteForm, ProveedorForm, ContactoForm, CuentaBancariaForm,
    GastoRecurrenteForm, OcurrenciaGastoForm, VentaProyectadaForm
)

from core.mixins import PlanFeatureRequiredMixin

# --- Obtener el modelo User activo ---
User = get_user_model()

# Configurar un logger
logger = logging.getLogger(__name__)


# ============================================
# ===       FUNCIONES HELPER               ===
# ============================================

def get_active_company_details(request):
    """
    Obtiene el ID, nombre y moneda de la empresa activa desde la sesión.
    Lanza PermissionDenied si no hay empresa activa o el usuario no pertenece.
    """
    empresa_id = request.session.get('empresa_activa_id')
    empresa_nombre = request.session.get('empresa_activa_nombre')
    moneda_base = request.session.get('empresa_activa_moneda')

    if not empresa_id:
        messages.warning(request, "Seleccione una empresa para continuar.")
        raise PermissionDenied("No hay empresa activa seleccionada.")

    if not request.user.is_authenticated:
         raise PermissionDenied("Usuario no autenticado.")

    # Verificar pertenencia
    if not request.user.empresas_asignadas.filter(empresa_id=empresa_id).exists():
         if 'empresa_activa_id' in request.session: del request.session['empresa_activa_id']
         if 'empresa_activa_nombre' in request.session: del request.session['empresa_activa_nombre']
         if 'empresa_activa_moneda' in request.session: del request.session['empresa_activa_moneda']
         messages.error(request, "Acceso denegado a la empresa seleccionada.")
         raise PermissionDenied("Usuario no asignado a la empresa activa en sesión.")

    if not moneda_base:
        try:
            empresa = Empresa.objects.get(pk=empresa_id)
            moneda_base = empresa.moneda
            request.session['empresa_activa_moneda'] = moneda_base
        except Empresa.DoesNotExist:
             raise PermissionDenied("La empresa activa seleccionada no existe.")

    return empresa_id, empresa_nombre, moneda_base

# --- Placeholder para Tasas de Cambio (REEMPLAZAR) ---
def get_tasa_cambio(moneda_origen, moneda_destino, fecha=None):
    if not moneda_origen or not moneda_destino or moneda_origen == moneda_destino: return Decimal('1.0')
    logger.debug(f"Buscando tasa: {moneda_origen} -> {moneda_destino} (Fecha: {fecha})")
    tasas_a_usd = {'COP': Decimal('0.00025'), 'EUR': Decimal('1.08'), 'PAB': Decimal('1.0'), 'USD': Decimal('1.0')}
    tasa_eur_usd = Decimal('1.08') # 1 EUR = X USD
    tasa_cop_usd = Decimal('0.00025') # 1 COP = X USD
    tasa_pab_usd = Decimal('1.0') # 1 PAB = X USD

    # Convertir origen a USD
    if moneda_origen == 'USD': valor_origen_en_usd = Decimal('1.0')
    elif moneda_origen == 'EUR': valor_origen_en_usd = tasa_eur_usd
    elif moneda_origen == 'COP': valor_origen_en_usd = tasa_cop_usd
    elif moneda_origen == 'PAB': valor_origen_en_usd = tasa_pab_usd
    else: logger.warning(f"Moneda origen desconocida: {moneda_origen}"); return Decimal('0.0')

    # Convertir USD a destino
    if moneda_destino == 'USD': valor_destino_desde_usd = Decimal('1.0')
    elif moneda_destino == 'EUR': valor_destino_desde_usd = Decimal('1.0') / tasa_eur_usd if tasa_eur_usd else 0
    elif moneda_destino == 'COP': valor_destino_desde_usd = Decimal('1.0') / tasa_cop_usd if tasa_cop_usd else 0
    elif moneda_destino == 'PAB': valor_destino_desde_usd = Decimal('1.0') / tasa_pab_usd if tasa_pab_usd else 0
    else: logger.warning(f"Moneda destino desconocida: {moneda_destino}"); return Decimal('0.0')

    if valor_destino_desde_usd > 0:
        tasa_final = valor_origen_en_usd * valor_destino_desde_usd
        # print(f"Tasa {moneda_origen}->{moneda_destino}: {tasa_final}")
        return tasa_final
    else:
        logger.warning(f"No se pudo calcular tasa de {moneda_origen} a {moneda_destino}")
        return Decimal('0.0')


def convertir_valor(monto, moneda_origen, moneda_destino, fecha=None):
    """Convierte un monto de una moneda a otra usando la tasa de cambio."""
    if monto is None or moneda_origen == moneda_destino: return Decimal(str(monto or '0.00'))
    monto_decimal = Decimal(str(monto))
    tasa = get_tasa_cambio(moneda_origen, moneda_destino, fecha)
    if tasa > 0:
        return (monto_decimal * tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        # No convertir si no hay tasa, devolver el original podría ser confuso
        # Devolver 0 o None indica que la conversión falló.
        logger.warning(f"Conversión fallida: No hay tasa para {moneda_origen} a {moneda_destino}. Monto original: {monto_decimal}")
        return None # Indicar fallo de conversión

# ============================================
# ===           VISTAS PRINCIPALES         ===
# ============================================

@login_required 
def dashboard_view(request):
    """Vista inicial del dashboard con KPIs y datos multi-moneda consolidados en moneda base."""
    try:
        empresa_id, empresa_nombre, moneda_base = get_active_company_details(request)
    except PermissionDenied:
        return redirect('core:selector_empresa')

    today = timezone.now().date()
    context = {
        'kpis': defaultdict(lambda: 0),
        'listas_rapidas': {'proximos_cobros': [], 'proximos_pagos': [], 'cobros_vencidos': []},
        'titulo_pagina': f'Dashboard ({empresa_nombre})',
        'moneda_base_display': moneda_base,
        'dashboard_chart_labels': json.dumps([]),
        'dashboard_chart_data_neto': json.dumps([]),
        'dashboard_chart_data_saldo': json.dumps([]),
    }
    kpis = context['kpis']
    listas_rapidas = context['listas_rapidas']
    grafico_data_labels = []
    grafico_data_neto = []
    grafico_data_saldo = []

    # --- 1. Calcular Saldos Bancarios ---
    saldo_base_total_calculado = Decimal('0.00')
    saldos_por_moneda_list = []
    error_saldos = False
    try:
        cuentas_empresa = CuentaBancaria.objects.filter(empresa_id=empresa_id)
        saldos_agrupados = cuentas_empresa.values('moneda').annotate(total_saldo=Sum('saldo_actual')).order_by('moneda')

        for saldo_info in saldos_agrupados:
            moneda_cta = saldo_info['moneda']
            total_saldo = saldo_info['total_saldo'] or Decimal('0.00')
            saldos_por_moneda_list.append({'moneda': moneda_cta, 'total_saldo': total_saldo})
            monto_convertido = convertir_valor(total_saldo, moneda_cta, moneda_base, today)
            saldo_base_total_calculado += monto_convertido

        kpis['saldos_por_moneda'] = saldos_por_moneda_list
        kpis['saldo_total_bancos_base'] = saldo_base_total_calculado

    except Exception:
        kpis['saldos_por_moneda'] = 'Error'
        kpis['saldo_total_bancos_base'] = 'Error'
        messages.error(request, "Error al calcular saldos bancarios.")
        logger.exception("Error saldos bancarios dash")
        saldo_base_total_calculado = Decimal('0.00')

    # --- 2. Calcular KPIs del Mes Actual ---
    try:
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        kpis['cobros_pendientes_mes_count'] = DetalleCuotaCobro.objects.filter(
            cobro__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__range=(today, end_of_month)
        ).count()
        kpis['pagos_pendientes_mes_count'] = (
            DetalleCuotaPago.objects.filter(
                pago__empresa_id=empresa_id,
                estatus='PEND',
                fecha_vencimiento__range=(today, end_of_month)
            ).count() +
            OcurrenciaGasto.objects.filter(
                gasto_recurrente__empresa_id=empresa_id,
                estatus='PEND',
                fecha_vencimiento__range=(today, end_of_month)
            ).count()
        )
        kpis['clientes_nuevos_mes'] = Cliente.objects.filter(
            empresa_id=empresa_id,
            creado_en__range=(start_of_month, end_of_month)
        ).count()

        kpis['total_vencido_cobrar_por_moneda'] = []
        kpis['total_vencido_cobrar_base'] = Decimal('0.00')
        vencidos_agg = DetalleCuotaCobro.objects.filter(
            cobro__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__lt=today
        ).values('cobro__moneda').annotate(total=Sum('monto_cuota')).order_by('cobro__moneda')
        for item in vencidos_agg:
            moneda = item['cobro__moneda']
            total = item['total'] or Decimal('0.00')
            kpis['total_vencido_cobrar_por_moneda'].append({'moneda': moneda, 'total': total})
            kpis['total_vencido_cobrar_base'] += convertir_valor(total, moneda, moneda_base, today)

        kpis['ventas_ganadas_mes_por_moneda'] = []
        kpis['ventas_ganadas_mes_base'] = Decimal('0.00')
        ventas_agg = VentaProyectada.objects.filter(
            empresa_id=empresa_id,
            estatus='GANA',
            fecha_cierre_estimada__range=(start_of_month, end_of_month)
        ).values('moneda').annotate(total=Sum('valor_total_estimado')).order_by('moneda')
        for item in ventas_agg:
            moneda = item['moneda']
            total = item['total'] or Decimal('0.00')
            kpis['ventas_ganadas_mes_por_moneda'].append({'moneda': moneda, 'total': total})
            kpis['ventas_ganadas_mes_base'] += convertir_valor(total, moneda, moneda_base, today)

    except Exception:
        messages.error(request, "Error KPIs.")
        logger.exception("Error KPIs dash")

    # --- 3. Proyecciones y Gráfico (Convertido a Moneda Base) ---
    saldo_acumulado_base = saldo_base_total_calculado
    saldo_minimo_base = saldo_acumulado_base
    fecha_saldo_minimo = today
    flujo_diario_base = OrderedDict()
    dias_horizonte = 30
    for i in range(dias_horizonte):
        fecha = today + timedelta(days=i)
        flujo_diario_base[fecha] = {'entradas_base': Decimal('0.00'), 'salidas_base': Decimal('0.00')}

    try:
        def procesar_y_convertir(queryset, fecha_field, monto_field, moneda_field):
            for item in queryset:
                fecha = item.get(fecha_field)
                monto = item.get(monto_field, Decimal('0.00'))
                moneda = item.get(moneda_field)
                if fecha and fecha in flujo_diario_base and moneda:
                    monto_conv = convertir_valor(monto, moneda, moneda_base, fecha)
                    yield fecha, monto_conv

        cobros_q = DetalleCuotaCobro.objects.filter(
            cobro__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__range=(today, today + timedelta(days=dias_horizonte - 1))
        ).values('fecha_vencimiento', 'monto_cuota', 'cobro__moneda')

        ventas_q = VentaProyectada.objects.filter(
            empresa_id=empresa_id,
            estatus='GANA',
            fecha_cierre_estimada__range=(today, today + timedelta(days=dias_horizonte - 1))
        ).values('fecha_cierre_estimada', 'valor_total_estimado', 'moneda')

        pagos_cuotas_q = DetalleCuotaPago.objects.filter(
            pago__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__range=(today, today + timedelta(days=dias_horizonte - 1))
        ).values('fecha_vencimiento', 'monto_cuota', 'pago__moneda')

        pagos_gastos_q = OcurrenciaGasto.objects.filter(
            gasto_recurrente__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__range=(today, today + timedelta(days=dias_horizonte - 1))
        ).values('fecha_vencimiento', 'monto', 'gasto_recurrente__moneda')

        for f, mc in procesar_y_convertir(cobros_q, 'fecha_vencimiento', 'monto_cuota', 'cobro__moneda'):
            flujo_diario_base[f]['entradas_base'] += mc
        for f, mc in procesar_y_convertir(ventas_q, 'fecha_cierre_estimada', 'valor_total_estimado', 'moneda'):
            flujo_diario_base[f]['entradas_base'] += mc
        for f, mc in procesar_y_convertir(pagos_cuotas_q, 'fecha_vencimiento', 'monto_cuota', 'pago__moneda'):
            flujo_diario_base[f]['salidas_base'] += mc
        for f, mc in procesar_y_convertir(pagos_gastos_q, 'fecha_vencimiento', 'monto', 'gasto_recurrente__moneda'):
            flujo_diario_base[f]['salidas_base'] += mc

        for i, (fecha, mov) in enumerate(flujo_diario_base.items()):
            neto_base = mov['entradas_base'] - mov['salidas_base']
            saldo_acumulado_base += neto_base
            grafico_data_labels.append(fecha.strftime('%d/%m'))
            grafico_data_neto.append(float(neto_base))
            grafico_data_saldo.append(float(saldo_acumulado_base))
            if saldo_acumulado_base < saldo_minimo_base:
                saldo_minimo_base = saldo_acumulado_base
                fecha_saldo_minimo = fecha
            if i == 6:
                kpis['saldo_proyectado_7d'] = saldo_acumulado_base
            if i == 14:
                kpis['saldo_proyectado_15d'] = saldo_acumulado_base
            if i == dias_horizonte - 1:
                kpis['saldo_proyectado_30d'] = saldo_acumulado_base

        kpis['saldo_minimo_proyectado'] = saldo_minimo_base
        kpis['fecha_saldo_minimo'] = fecha_saldo_minimo

    except Exception:
        messages.error(request, "Error proyecciones.")
        logger.exception("Error proyecciones dash")

    # --- 4. Listas rápidas ---
    try:
        listas_rapidas['proximos_cobros'] = DetalleCuotaCobro.objects.filter(
            cobro__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__gte=today
        ).select_related('cobro', 'cobro__cliente').order_by('fecha_vencimiento')[:5]

        ppc = DetalleCuotaPago.objects.filter(
            pago__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__gte=today
        ).select_related('pago', 'pago__proveedor').values(
            'pk', 'fecha_vencimiento', 'monto_cuota', 'pago__moneda', 'pago__proveedor__nombre',
            pago_tipo=models.Value('Pago Proveedor', output_field=models.CharField())
        )
        pg = OcurrenciaGasto.objects.filter(
            gasto_recurrente__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__gte=today
        ).select_related('gasto_recurrente').values(
            'pk', 'fecha_vencimiento', monto_cuota=F('monto'), pago__moneda=F('gasto_recurrente__moneda'),
            pago__proveedor__nombre=F('gasto_recurrente__descripcion'),
            pago_tipo=models.Value('Gasto Recurrente', output_field=models.CharField())
        )
        lpc = sorted(list(ppc) + list(pg), key=lambda x: x['fecha_vencimiento'])
        listas_rapidas['proximos_pagos'] = lpc[:5]

        listas_rapidas['cobros_vencidos'] = DetalleCuotaCobro.objects.filter(
            cobro__empresa_id=empresa_id,
            estatus='PEND',
            fecha_vencimiento__lt=today
        ).select_related('cobro', 'cobro__cliente').order_by('-fecha_vencimiento')[:5]

    except Exception:
        messages.error(request, "Error listas rápidas.")
        logger.exception("Error listas rápidas dash")

    # --- 5. Asignar datos al contexto ---
    context['dashboard_chart_labels'] = json.dumps(grafico_data_labels)
    context['dashboard_chart_data_neto'] = json.dumps(grafico_data_neto)
    context['dashboard_chart_data_saldo'] = json.dumps(grafico_data_saldo)

    return render(request, 'gestion/dashboard.html', context)

@login_required
def flujo_efectivo_report_view(request):
    """
    Genera informe de flujo proyectado, consolidado en moneda base
    O filtrado y consolidado en una moneda específica si se pasa por GET.
    """
    try:
        empresa_id, empresa_nombre, moneda_base_empresa = get_active_company_details(request)
    except PermissionDenied:
        return redirect('core:selector_empresa')

    today = timezone.now().date()
    default_end_date = today + timedelta(days=30)

    # --- 1. Obtener y Validar Parámetros (Fecha y Moneda Filtro) ---
    start_date_str = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date_str = request.GET.get('end_date', default_end_date.strftime('%Y-%m-%d'))
    moneda_filtro = request.GET.get('moneda', '').upper() or None # Obtener moneda del filtro

    try: start_date = date.fromisoformat(start_date_str)
    except ValueError: start_date = today # Default si inválido
    try: end_date = date.fromisoformat(end_date_str)
    except ValueError: end_date = default_end_date
    if end_date < start_date: end_date = start_date + timedelta(days=30)

    # Determinar la moneda en la que se mostrará el reporte
    moneda_reporte = moneda_filtro if moneda_filtro else moneda_base_empresa
    mostrar_agregado = not moneda_filtro # True si estamos mostrando agregado en moneda base

    # --- 2. Calcular Saldo Inicial (Convertido a Moneda del Reporte) ---
    saldo_inicial_reporte = Decimal('0.00')
    saldos_originales_info = [] # Para mostrar detalle si es necesario
    try:
        cuentas_empresa = CuentaBancaria.objects.filter(empresa_id=empresa_id)
        # Si filtramos por moneda, solo considerar cuentas de esa moneda
        if moneda_filtro:
            cuentas_empresa = cuentas_empresa.filter(moneda=moneda_filtro)

        saldos_cuentas = cuentas_empresa.values('moneda', 'saldo_actual')
        for cuenta in saldos_cuentas:
            moneda_cta = cuenta['moneda']
            saldo_cta = cuenta.get('saldo_actual', Decimal('0.00'))
            saldos_originales_info.append({'moneda': moneda_cta, 'saldo': saldo_cta}) # Guardar original

            # Convertir a la moneda del reporte (sea la base o la filtrada)
            monto_convertido = convertir_valor(saldo_cta, moneda_cta, moneda_reporte, today)
            if monto_convertido is not None:
                 saldo_inicial_reporte += monto_convertido
            elif not moneda_filtro: # Solo advertir si estamos consolidando y falla
                 messages.warning(request, f"No se pudo convertir saldo de {moneda_cta} a {moneda_reporte}.")
    except Exception as e:
        saldo_inicial_reporte = Decimal('0.00'); messages.error(request,"Error saldo inicial."); logger.exception("Error saldo inicial reporte flujo")

    # --- 3, 4 y 5: Obtener Movimientos, Estructurar y Calcular Flujo (en Moneda Reporte) ---
    reporte_periodos = []
    saldo_acumulado_reporte = saldo_inicial_reporte

    try:
        flujo_diario_reporte = OrderedDict()
        dias_a_procesar = (end_date - start_date).days + 1
        for i in range(dias_a_procesar): flujo_diario_reporte[start_date + timedelta(days=i)] = {'entradas': Decimal('0.00'), 'salidas': Decimal('0.00')}

        # Obtener Querysets Base filtrados por empresa y rango
        cobros_q_base = DetalleCuotaCobro.objects.filter(cobro__empresa_id=empresa_id, estatus='PEND', fecha_vencimiento__range=(start_date, end_date))
        ventas_q_base = VentaProyectada.objects.filter(empresa_id=empresa_id, estatus='GANA', fecha_cierre_estimada__range=(start_date, end_date))
        pagos_cuotas_q_base = DetalleCuotaPago.objects.filter(pago__empresa_id=empresa_id, estatus='PEND', fecha_vencimiento__range=(start_date, end_date))
        pagos_gastos_q_base = OcurrenciaGasto.objects.filter(gasto_recurrente__empresa_id=empresa_id, estatus='PEND', fecha_vencimiento__range=(start_date, end_date))

        # Si hay filtro de moneda, filtrar más los querysets
        if moneda_filtro:
            cobros_q = cobros_q_base.filter(cobro__moneda=moneda_filtro).values('fecha_vencimiento', 'monto_cuota')
            ventas_q = ventas_q_base.filter(moneda=moneda_filtro).values('fecha_cierre_estimada', 'valor_total_estimado')
            pagos_cuotas_q = pagos_cuotas_q_base.filter(pago__moneda=moneda_filtro).values('fecha_vencimiento', 'monto_cuota')
            pagos_gastos_q = pagos_gastos_q_base.filter(gasto_recurrente__moneda=moneda_filtro).values('fecha_vencimiento', 'monto')
            # En este caso, no necesitamos conversión porque todo está en moneda_filtro == moneda_reporte
            tasa_conversion = Decimal('1.0')
        else:
            # Si NO hay filtro, obtenemos todos y necesitamos la moneda para convertir
            cobros_q = cobros_q_base.values('fecha_vencimiento', 'monto_cuota', 'cobro__moneda')
            ventas_q = ventas_q_base.values('fecha_cierre_estimada', 'valor_total_estimado', 'moneda')
            pagos_cuotas_q = pagos_cuotas_q_base.values('fecha_vencimiento', 'monto_cuota', 'pago__moneda')
            pagos_gastos_q = pagos_gastos_q_base.values('fecha_vencimiento', 'monto', 'gasto_recurrente__moneda')
            # La conversión se hará item por item

        # Llenar diccionario (ya sea con valores originales o convertidos)
        for item in cobros_q:
            fecha=item.get('fecha_vencimiento'); monto=item.get('monto_cuota',0); moneda_orig=item.get('cobro__moneda') if not moneda_filtro else moneda_filtro
            if fecha and fecha in flujo_diario_reporte and moneda_orig:
                monto_conv = convertir_valor(monto, moneda_orig, moneda_reporte, fecha)
                if monto_conv is not None: flujo_diario_reporte[fecha]['entradas'] += monto_conv
        for item in ventas_q:
            fecha=item.get('fecha_cierre_estimada'); monto=item.get('valor_total_estimado',0); moneda_orig=item.get('moneda') if not moneda_filtro else moneda_filtro
            if fecha and fecha in flujo_diario_reporte and moneda_orig:
                monto_conv = convertir_valor(monto, moneda_orig, moneda_reporte, fecha)
                if monto_conv is not None: flujo_diario_reporte[fecha]['entradas'] += monto_conv
        for item in pagos_cuotas_q:
            fecha=item.get('fecha_vencimiento'); monto=item.get('monto_cuota',0); moneda_orig=item.get('pago__moneda') if not moneda_filtro else moneda_filtro
            if fecha and fecha in flujo_diario_reporte and moneda_orig:
                monto_conv = convertir_valor(monto, moneda_orig, moneda_reporte, fecha)
                if monto_conv is not None: flujo_diario_reporte[fecha]['salidas'] += monto_conv
        for item in pagos_gastos_q:
            fecha=item.get('fecha_vencimiento'); monto=item.get('monto',0); moneda_orig=item.get('gasto_recurrente__moneda') if not moneda_filtro else moneda_filtro
            if fecha and fecha in flujo_diario_reporte and moneda_orig:
                monto_conv = convertir_valor(monto, moneda_orig, moneda_reporte, fecha)
                if monto_conv is not None: flujo_diario_reporte[fecha]['salidas'] += monto_conv

        # Calcular flujo neto y saldo acumulado (todo en moneda_reporte)
        for fecha, mov in flujo_diario_reporte.items():
            neto = mov['entradas'] - mov['salidas']; saldo_acumulado_reporte += neto
            reporte_periodos.append({'fecha':fecha,'entradas':mov['entradas'],'salidas':mov['salidas'],'flujo_neto':neto,'saldo_proyectado':saldo_acumulado_reporte})

    except Exception as e:
        messages.error(request,"Error al calcular flujo diario.")
        logger.exception("Error calculando flujo diario reporte")
        reporte_periodos = []

    # --- 6. Preparar Contexto Final ---
    context = {
        'start_date': start_date, 'end_date': end_date,
        'saldo_inicial': saldo_inicial_reporte, # Saldo inicial en moneda reporte
        'reporte_periodos': reporte_periodos, # Valores en moneda reporte
        'titulo_pagina': f'Flujo de Efectivo ({empresa_nombre})',
        'moneda_reporte_display': moneda_reporte, # Moneda de este reporte
        'es_simulacion': False,
        'filtros': request.GET.copy() # Pasar filtros GET a plantilla
    }
    return render(request, 'gestion/flujo_efectivo_report.html', context)

@login_required
def simulacion_flujo_view(request):
    """
    Genera informe de flujo proyectado APLICANDO SIMULACIÓN, consolidado
    en moneda base o filtrado y consolidado en una moneda específica.
    """
    try:
        empresa_id, empresa_nombre, moneda_base_empresa = get_active_company_details(request)
    except PermissionDenied:
        return redirect('core:selector_empresa')

    today = timezone.now().date()
    default_end_date = today + timedelta(days=30)

    # --- 1. Obtener y Validar Parámetros (Fecha, Moneda Filtro, Simulación) ---
    start_date_str = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date_str = request.GET.get('end_date', default_end_date.strftime('%Y-%m-%d'))
    moneda_filtro = request.GET.get('moneda', '').upper() or None
    try: start_date = date.fromisoformat(start_date_str)
    except ValueError: start_date = today
    try: end_date = date.fromisoformat(end_date_str)
    except ValueError: end_date = default_end_date
    if end_date < start_date: end_date = start_date + timedelta(days=30)

    # Parámetros de Simulación (con validación)
    pct_cobro_str = request.GET.get('pct_cobro', '100'); pct_cobro = Decimal('100')
    try: 
        v_temp = Decimal(pct_cobro_str)
        if 0 <= v_temp <= 100: pct_cobro=v_temp
    except (InvalidOperation,TypeError): pass
    excluir_pago_id_str = request.GET.get('excluir_pago_id', ''); excluir_pago_id = None
    try:
        if excluir_pago_id_str: excluir_pago_id = int(excluir_pago_id_str)
    except ValueError: pass
    excluir_gasto_id_str = request.GET.get('excluir_gasto_id', ''); excluir_gasto_id = None
    try:
        if excluir_gasto_id_str: excluir_gasto_id = int(excluir_gasto_id_str)
    except ValueError: pass

    # Determinar moneda del reporte
    moneda_reporte = moneda_filtro if moneda_filtro else moneda_base_empresa

    # --- 2. Calcular Saldo Inicial (Convertido a Moneda del Reporte) ---
    saldo_inicial_reporte = Decimal('0.00')
    try:
        cuentas_q = CuentaBancaria.objects.filter(empresa_id=empresa_id)
        if moneda_filtro: cuentas_q = cuentas_q.filter(moneda=moneda_filtro)
        for cuenta in cuentas_q.values('moneda', 'saldo_actual'):
            monto_conv = convertir_valor(cuenta['saldo_actual'], cuenta['moneda'], moneda_reporte, today)
            if monto_conv is not None: saldo_inicial_reporte += monto_conv
            # else: messages.warning(...) # Omitir warning repetitivo aquí
    except Exception as e: messages.error(request,"Error saldo inicial."); logger.exception("Error saldo simulación")

    # --- 3, 4 y 5: Obtener Movimientos, Aplicar Simulación, Convertir, Estructurar y Calcular Flujo ---
    reporte_periodos = []
    saldo_acumulado_reporte = saldo_inicial_reporte

    try:
        flujo_diario_reporte = OrderedDict()
        dias_a_procesar = (end_date - start_date).days + 1
        for i in range(dias_a_procesar): flujo_diario_reporte[start_date + timedelta(days=i)] = {'entradas': Decimal('0.00'), 'salidas': Decimal('0.00')}

        factor_cobro = pct_cobro / 100

        # Querysets Base (filtrados por empresa y rango)
        cobros_q_base = DetalleCuotaCobro.objects.filter(cobro__empresa_id=empresa_id, estatus='PEND', fecha_vencimiento__range=(start_date, end_date))
        ventas_q_base = VentaProyectada.objects.filter(empresa_id=empresa_id, estatus='GANA', fecha_cierre_estimada__range=(start_date, end_date))
        pagos_cuotas_q_base = DetalleCuotaPago.objects.filter(pago__empresa_id=empresa_id, estatus='PEND', fecha_vencimiento__range=(start_date, end_date))
        pagos_gastos_q_base = OcurrenciaGasto.objects.filter(gasto_recurrente__empresa_id=empresa_id, estatus='PEND', fecha_vencimiento__range=(start_date, end_date))

        # Aplicar filtros adicionales (exclusiones y moneda si aplica)
        if excluir_pago_id: pagos_cuotas_q_base = pagos_cuotas_q_base.exclude(id=excluir_pago_id)
        if excluir_gasto_id: pagos_gastos_q_base = pagos_gastos_q_base.exclude(id=excluir_gasto_id)

        if moneda_filtro:
            cobros_q = cobros_q_base.filter(cobro__moneda=moneda_filtro).values('fecha_vencimiento', 'monto_cuota')
            ventas_q = ventas_q_base.filter(moneda=moneda_filtro).values('fecha_cierre_estimada', 'valor_total_estimado')
            pagos_cuotas_q = pagos_cuotas_q_base.filter(pago__moneda=moneda_filtro).values('fecha_vencimiento', 'monto_cuota')
            pagos_gastos_q = pagos_gastos_q_base.filter(gasto_recurrente__moneda=moneda_filtro).values('fecha_vencimiento', 'monto')
        else:
            # Obtener con moneda original para conversión
            cobros_q = cobros_q_base.values('fecha_vencimiento', 'monto_cuota', 'cobro__moneda')
            ventas_q = ventas_q_base.values('fecha_cierre_estimada', 'valor_total_estimado', 'moneda')
            pagos_cuotas_q = pagos_cuotas_q_base.values('fecha_vencimiento', 'monto_cuota', 'pago__moneda')
            pagos_gastos_q = pagos_gastos_q_base.values('fecha_vencimiento', 'monto', 'gasto_recurrente__moneda')

        # Función interna helper para procesar, aplicar simulación y convertir
        def procesar_simular_convertir(queryset, fecha_field, monto_field, moneda_field, es_entrada=True):
            for item in queryset:
                fecha = item.get(fecha_field); monto_orig = item.get(monto_field, 0); moneda_orig = item.get(moneda_field) if not moneda_filtro else moneda_filtro
                if fecha and fecha in flujo_diario_reporte and moneda_orig:
                    # Aplicar simulación (pct_cobro) SOLO a entradas
                    monto_simulado = monto_orig * factor_cobro if es_entrada else monto_orig
                    # Convertir a moneda reporte
                    monto_conv = convertir_valor(monto_simulado, moneda_orig, moneda_reporte, fecha)
                    if monto_conv is not None: yield fecha, monto_conv

        # Llenar diccionario
        for fecha, monto_conv in procesar_simular_convertir(cobros_q, 'fecha_vencimiento', 'monto_cuota', 'cobro__moneda', True):
            flujo_diario_reporte[fecha]['entradas'] += monto_conv
        for fecha, monto_conv in procesar_simular_convertir(ventas_q, 'fecha_cierre_estimada', 'valor_total_estimado', 'moneda', True):
            flujo_diario_reporte[fecha]['entradas'] += monto_conv
        for fecha, monto_conv in procesar_simular_convertir(pagos_cuotas_q, 'fecha_vencimiento', 'monto_cuota', 'pago__moneda', False):
            flujo_diario_reporte[fecha]['salidas'] += monto_conv
        for fecha, monto_conv in procesar_simular_convertir(pagos_gastos_q, 'fecha_vencimiento', 'monto', 'gasto_recurrente__moneda', False):
             flujo_diario_reporte[fecha]['salidas'] += monto_conv

        # Calcular flujo neto y saldo acumulado (en moneda_reporte)
        for fecha, mov in flujo_diario_reporte.items():
            neto = mov['entradas'] - mov['salidas']; saldo_acumulado_reporte += neto
            reporte_periodos.append({'fecha':fecha,'entradas':mov['entradas'],'salidas':mov['salidas'],'flujo_neto':neto,'saldo_proyectado':saldo_acumulado_reporte})

    except Exception as e:
        messages.error(request,"Error al procesar datos diarios para simulación.")
        logger.exception("Error procesando flujo diario simulacion")
        reporte_periodos = []

    # --- 6. Preparar Contexto Final ---
    context = {
        'start_date': start_date, 'end_date': end_date,
        'saldo_inicial': saldo_inicial_reporte, # Saldo inicial en moneda reporte
        'reporte_periodos': reporte_periodos, # Valores en moneda reporte
        'titulo_pagina': f'Simulación Flujo ({empresa_nombre})',
        'moneda_reporte_display': moneda_reporte, # Moneda de este reporte
        'es_simulacion': True,
        # Pasar filtros y params de simulación para mantenerlos en el form
        'filtros': request.GET.copy(), # Incluye fechas y moneda
        'pct_cobro_actual': pct_cobro,
        'excluir_pago_id_actual': excluir_pago_id,
        'excluir_gasto_id_actual': excluir_gasto_id,
    }
    return render(request, 'gestion/flujo_efectivo_report.html', context)

# --- Vista Pipeline Kanban (Filtrada por empresa) ---
@login_required
def pipeline_view(request):
    """Muestra las ventas proyectadas en un tablero Kanban por estatus."""
    try:
        empresa_id, empresa_nombre, moneda_base = get_active_company_details(request)
    except PermissionDenied:
        # Si falla la obtención de empresa, redirigir al selector
        return redirect('core:selector_empresa') # Asegúrate que 'core:selector_empresa' sea la URL correcta

    # --- Definir Orden de Estatus Completo ---
    # Usar los valores Enum directamente, Django los manejará como claves
    orden_estatus = [
        VentaProyectada.EstatusVenta.PROSPECTO,
        VentaProyectada.EstatusVenta.CALIFICADO,
        VentaProyectada.EstatusVenta.PROPUESTA,
        VentaProyectada.EstatusVenta.NEGOCIACION,
        VentaProyectada.EstatusVenta.GANADA,
        VentaProyectada.EstatusVenta.APLAZADA,
        VentaProyectada.EstatusVenta.PERDIDA, # Incluir todos los estados posibles
    ]

    # --- Obtener Oportunidades Filtradas por Empresa Activa ---
    try:
        # Filtrar por empresa_id obtenido de la sesión/helper
        oportunidades = VentaProyectada.objects.filter(
            empresa_id=empresa_id
        ).select_related( # Optimizar carga de datos relacionados
            'cliente', 'asesor_comercial'
        ).order_by( # Ordenar dentro de las columnas (opcional)
            'fecha_cierre_estimada', 'valor_total_estimado'
        )
        # DEBUG: Imprimir para verificar si se obtienen datos
        # print(f"Oportunidades encontradas ({empresa_nombre}): {oportunidades.count()}")
        # for op_debug in oportunidades:
        #    print(f"- ID: {op_debug.id}, Estatus: {op_debug.estatus}, Desc: {op_debug.descripcion[:20]}")

    except Exception as e:
        messages.error(request, "Error al obtener las oportunidades de venta.")
        logger.exception(f"Error obteniendo VentasProyectadas para empresa {empresa_id}")
        oportunidades = VentaProyectada.objects.none() # Devolver queryset vacío si hay error

    # --- Agrupar Oportunidades por Estatus ---
    pipeline_data = OrderedDict()
    # Inicializar todas las columnas/estados definidos en orden_estatus
    for estatus_val in orden_estatus:
        try:
            # Usar .label para obtener el nombre legible del Choice
            nombre_estatus = VentaProyectada.EstatusVenta(estatus_val).label
        except ValueError:
            # Fallback si el valor no es un miembro válido (poco probable si orden_estatus usa el Enum)
            nombre_estatus = str(estatus_val).replace('_', ' ').title()
            logger.warning(f"Valor de estatus no encontrado en Enum: {estatus_val}")

        pipeline_data[estatus_val] = {
            'nombre': nombre_estatus,
            'oportunidades': [],
            'total_valor': Decimal('0.00'),
            'total_ponderado': Decimal('0.00'),
        }

    # Llenar la estructura agrupada
    if oportunidades: # Solo iterar si se obtuvieron oportunidades
        for op in oportunidades:
            estatus_actual = op.estatus # Este será el valor corto ('PROS', 'CALI', etc.)
            if estatus_actual in pipeline_data: # Comprobar si el estado actual está en nuestro diccionario ordenado
                pipeline_data[estatus_actual]['oportunidades'].append(op)
                pipeline_data[estatus_actual]['total_valor'] += (op.valor_total_estimado or Decimal('0.00'))
                pipeline_data[estatus_actual]['total_ponderado'] += op.valor_ponderado # Usar la propiedad @property
            else:
                # Si por alguna razón el estatus no está en orden_estatus (debería estar), agrupar en 'Otros'
                logger.warning(f"Estatus '{estatus_actual}' de Venta {op.pk} no mapeado en orden_estatus. Agrupando en Otros.")
                if 'OTROS' not in pipeline_data:
                     pipeline_data['OTROS'] = {'nombre': 'Otros/Desconocido', 'oportunidades': [], 'total_valor': Decimal('0.00'), 'total_ponderado': Decimal('0.00')}
                pipeline_data['OTROS']['oportunidades'].append(op)
                pipeline_data['OTROS']['total_valor'] += (op.valor_total_estimado or Decimal('0.00'))
                pipeline_data['OTROS']['total_ponderado'] += op.valor_ponderado

    # --- Preparar Contexto y Renderizar ---
    context = {
        'pipeline_data': pipeline_data,
        'titulo_pagina': f'Pipeline de Ventas ({empresa_nombre})', # Incluir nombre empresa en título
        'moneda_base_display': moneda_base, # Pasar moneda para usar en totales si es necesario
    }
    return render(request, 'gestion/pipeline.html', context)

# --- Vista Conversión Venta a Cobro (Ya debería estar filtrada implícitamente por empresa) ---
@login_required
@permission_required('gestion.add_cobro', raise_exception=True, login_url=reverse_lazy('login'))
def convertir_a_cobro_view(request, venta_id):
    try: empresa_id, _, _ = get_active_company_details(request)
    except PermissionDenied: return redirect('core:selector_empresa')
    # Filtrar por pk Y empresa activa para seguridad
    venta_proyectada = get_object_or_404(VentaProyectada.objects.select_related('cliente','asesor_comercial'), pk=venta_id, empresa_id=empresa_id)
    # ... (Resto de la lógica como antes, la empresa se asigna al crear Cobro) ...
    if vp.estatus!=VentaProyectada.EstatusVenta.GANADA: messages.error(request,"Error: Solo 'Ganadas'."); return redirect(reverse('admin:gestion_ventaproyectada_changelist')) # O al pipeline
    cobro_existente=Cobro.objects.filter(venta_proyectada_origen=vp).first() # Ya filtrado por empresa via vp
    if cobro_existente:
        messages.warning(request,f"Advertencia: Cobro ya existe p/ Venta '{vp.id}'.");
        try: url=reverse('gestion:cobro_update', args=[cobro_existente.pk])
        except: url=reverse('admin:gestion_cobro_change', args=[cobro_existente.pk])
        return redirect(url)
    try:
        nc=Cobro(..., empresa_id=empresa_id, creado_por=request.user); nc.save(); # Asegurar asignar empresa
        messages.success(request,f"Cobro creado p/ Venta '{vp.id}'. Complete.");
        try: url=reverse('gestion:cobro_update', args=[nc.pk])
        except: url=reverse('admin:gestion_cobro_change', args=[nc.pk])
        return redirect(url)
    except Exception as e: logger.exception(f"Error conversión Venta {venta_id}"); messages.error(request,"Error inesperado."); return redirect(reverse('admin:gestion_ventaproyectada_changelist'))


# ============================================
# ===   MIXINS PARA VISTAS POR EMPRESA     ===
# ============================================
class FilteredByCompanyMixin:
    """
    Mixin base para obtener detalles de la empresa activa y manejar PermissionDenied.
    Las clases hijas deben implementar el filtrado específico en get_queryset.
    """
    empresa_id = None
    empresa_nombre = None
    moneda_base = None

    def dispatch(self, request, *args, **kwargs):
        try:
            self.empresa_id, self.empresa_nombre, self.moneda_base = get_active_company_details(request)
        except PermissionDenied:
            # Redirigir al selector o mostrar error 403
            # return redirect('core:selector_empresa')
            raise PermissionDenied("Acceso denegado o empresa no seleccionada.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset_base(self):
        """Devuelve el queryset inicial filtrado por empresa."""
        # Determinar el campo de relación con empresa (puede variar)
        # Asume 'empresa_id' o 'modelo_padre__empresa_id'
        filter_kwargs = {}
        if hasattr(self.model, 'empresa'):
             filter_kwargs = {'empresa_id': self.empresa_id}
        elif hasattr(self.model, 'cobro') and hasattr(Cobro, 'empresa'):
             filter_kwargs = {'cobro__empresa_id': self.empresa_id}
        elif hasattr(self.model, 'pago') and hasattr(Pago, 'empresa'):
             filter_kwargs = {'pago__empresa_id': self.empresa_id}
        elif hasattr(self.model, 'gasto_recurrente') and hasattr(GastoRecurrente, 'empresa'):
             filter_kwargs = {'gasto_recurrente__empresa_id': self.empresa_id}
        # Añadir más casos si es necesario

        if not filter_kwargs:
             logger.error(f"No se pudo determinar cómo filtrar {self.model.__name__} por empresa.")
             return self.model.objects.none() # Devolver vacío si no se sabe filtrar

        return self.model.objects.filter(**filter_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['empresa_activa_nombre'] = self.empresa_nombre
        context['moneda_base_display'] = self.moneda_base
        if 'titulo_pagina' not in context:
             try:
                 # Título por defecto más inteligente
                 object_name = self.object._meta.verbose_name.capitalize() if hasattr(self, 'object') and self.object else self.model._meta.verbose_name.capitalize()
                 view_type = "Detalle" if isinstance(self, DetailView) else "Listado" if isinstance(self, ListView) else "Formulario"
                 context['titulo_pagina'] = f"{view_type} {object_name}"
                 if hasattr(self, 'object') and self.object:
                      context['titulo_pagina'] += f": {str(self.object)[:30]}{'...' if len(str(self.object))>30 else ''}"
             except:
                 context['titulo_pagina'] = self.model._meta.verbose_name_plural.capitalize()
        return context


class FilteredByCompanyListView(FilteredByCompanyMixin, LoginRequiredMixin, ListView):
    paginate_by = 15
    search_fields = [] # Definir en la clase hija

    def get_queryset(self):
        qs = self.get_queryset_base() # Obtener filtrado por empresa
        # Añadir optimizaciones estándar
        if hasattr(self.model, 'empresa'): qs = qs.select_related('empresa')
        if hasattr(self.model, 'cliente'): qs = qs.select_related('cliente')
        if hasattr(self.model, 'proveedor'): qs = qs.select_related('proveedor')
        if hasattr(self.model, 'responsable_seguimiento'): qs = qs.select_related('responsable_seguimiento')
        if hasattr(self.model, 'responsable_pago'): qs = qs.select_related('responsable_pago')
        if hasattr(self.model, 'gasto_recurrente'): qs = qs.select_related('gasto_recurrente')
        if hasattr(self.model, 'tags'): qs = qs.prefetch_related('tags')

        # Aplicar búsqueda genérica
        query = self.request.GET.get('q')
        if query and self.search_fields:
            q_objects = Q()
            for field in self.search_fields:
                q_objects |= Q(**{f"{field}__icontains": query})
            qs = qs.filter(q_objects).distinct()

        # Ordenamiento por defecto (la clase hija puede sobrescribirlo)
        ordering = getattr(self.model._meta, 'ordering', None)
        if ordering:
            qs = qs.order_by(*ordering)
        elif hasattr(self.model, 'nombre'):
             qs = qs.order_by('nombre')
        elif hasattr(self.model, 'fecha_creacion'):
             qs = qs.order_by('-fecha_creacion')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['filtros'] = self.request.GET.copy()
        # Quitar 'page' de los filtros para la paginación
        context['filtros'].pop('page', None)
        return context


class FilteredByCompanyDetailView(FilteredByCompanyMixin, LoginRequiredMixin, DetailView):
     # get_queryset en el mixin ya filtra por empresa
     # get_context_data en el mixin ya añade datos de empresa/moneda y título básico
     # Las clases hijas deben sobrescribir get_queryset para añadir select/prefetch
     # y get_context_data para añadir título específico o datos extra
     pass


class FilteredByCompanyCreateView(FilteredByCompanyMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    # get_form_kwargs inyecta empresa_id
    # form_valid asigna empresa y usuario

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa_id'] = self.empresa_id # Usar el atributo del mixin
        return kwargs

    def form_valid(self, form):
        form.instance.empresa_id = self.empresa_id
        if hasattr(form.instance, 'creado_por') and not form.instance.creado_por:
            form.instance.creado_por = self.request.user
        if hasattr(form.instance, 'actualizado_por'): # Asignar también al crear
            form.instance.actualizado_por = self.request.user
        messages.success(self.request, f"{self.model._meta.verbose_name.capitalize()} registrado/a.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
         context = super().get_context_data(**kwargs)
         if 'titulo_pagina' not in context:
              context['titulo_pagina'] = f"Registrar Nuevo {self.model._meta.verbose_name.capitalize()}"
         return context


class FilteredByCompanyUpdateView(FilteredByCompanyMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    # get_queryset en el mixin ya filtra por empresa
    # get_form_kwargs inyecta empresa_id

     def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empresa_id'] = self.empresa_id
        return kwargs

     def form_valid(self, form):
        if hasattr(form.instance, 'actualizado_por'):
            form.instance.actualizado_por = self.request.user
        messages.success(self.request, f"{self.model._meta.verbose_name.capitalize()} actualizado/a.")
        return super().form_valid(form)

     def get_context_data(self, **kwargs):
         context = super().get_context_data(**kwargs)
         if 'titulo_pagina' not in context and self.object:
              context['titulo_pagina'] = f"Editar {self.model._meta.verbose_name.capitalize()}: {str(self.object)[:30]}{'...' if len(str(self.object))>30 else ''}"
         elif 'titulo_pagina' not in context:
              context['titulo_pagina'] = f"Editar {self.model._meta.verbose_name.capitalize()}"
         return context


class FilteredByCompanyDeleteView(FilteredByCompanyMixin, LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    success_message = "Registro eliminado exitosamente."
    # get_queryset en el mixin ya filtra por empresa

    def post(self, request, *args, **kwargs):
        # Sobrescribir post para poder añadir el mensaje ANTES de borrar el objeto
        self.object = self.get_object() # Necesario para que el mensaje pueda usar el objeto si se personaliza
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, self.success_message)
        return redirect(success_url)

    # get_context_data heredado del mixin está bien


# ============================================
# ===       VISTAS CRUD (Refactorizadas)   ===
# ============================================

# --- CRUD Cobros ---
class CobroListView(FilteredByCompanyListView):
    model = Cobro; template_name = 'gestion/cobro_list.html'; context_object_name = 'cobros';
    search_fields = ['numero_documento', 'cliente__nombre', 'grupo_concepto']
    def get_queryset(self): return super().get_queryset().select_related('cliente', 'responsable_seguimiento').order_by('-fecha_factura')

class CobroDetailView(FilteredByCompanyDetailView):
    model = Cobro; template_name = 'gestion/cobro_detail.html'; context_object_name = 'cobro'
    def get_queryset(self): return super().get_queryset().select_related('cliente', 'vendedor', 'responsable_seguimiento', 'venta_proyectada_origen', 'creado_por', 'actualizado_por').prefetch_related(models.Prefetch('cuotas', queryset=DetalleCuotaCobro.objects.select_related('cuenta_bancaria_deposito').order_by('numero_cuota')))

class CobroCreateView(FilteredByCompanyCreateView):
    model = Cobro; form_class = CobroForm; template_name = 'gestion/cobro_form.html';
    success_url = reverse_lazy('gestion:cobro_list'); permission_required = 'gestion.add_cobro'

class CobroUpdateView(FilteredByCompanyUpdateView):
    model = Cobro; form_class = CobroForm; template_name = 'gestion/cobro_form.html';
    success_url = reverse_lazy('gestion:cobro_list'); permission_required = 'gestion.change_cobro'
    CuotaFormSet = inlineformset_factory(Cobro, DetalleCuotaCobro, form=DetalleCuotaCobroForm, extra=0, can_delete=False, fk_name='cobro')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); prefix='cuotas'
        if self.request.POST: ctx['cuota_formset'] = self.CuotaFormSet(self.request.POST, instance=self.object, prefix=prefix)
        else: ctx['cuota_formset'] = self.CuotaFormSet(instance=self.object, prefix=prefix)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data(); cuota_formset = ctx['cuota_formset']
        if form.is_valid() and cuota_formset.is_valid():
            response = super().form_valid(form) # Llama al form_valid del mixin (guarda y pone mensaje)
            # Guardar formset después del objeto principal
            cuota_formset.instance = self.object # self.object ya está guardado por el mixin
            cuota_formset.save()
            try: self.validar_suma_cuotas_post_save(self.object)
            except ValidationError as e: messages.error(self.request,f"Error Validación: {e}"); return self.render_to_response(self.get_context_data(form=form,cuota_formset=cuota_formset))
            self.actualizar_estatus_cobro(self.object)
            # El mensaje de éxito principal ya se puso en el mixin, podríamos añadir uno específico
            # messages.success(self.request,"Cobro y cuotas actualizados.")
            return response # Devolver la redirección del padre
        else:
             if not form.is_valid(): logger.warning(f"Errores CobroForm PK {self.object.pk}: {form.errors.as_json()}")
             if not cuota_formset.is_valid(): logger.warning(f"Errores CuotaFormSet PK {self.object.pk}: {cuota_formset.errors}"); logger.warning(f"Non-form CuotaFormSet errors: {cuota_formset.non_form_errors()}")
             messages.error(self.request,"Corrija los errores indicados.")
             return self.render_to_response(self.get_context_data(form=form,cuota_formset=cuota_formset))

    # Métodos helper específicos
    def validar_suma_cuotas_post_save(self, cobro_instance): ... # Mantener como antes
    def actualizar_estatus_cobro(self, cobro_instance): ... # Mantener como antes
    def get_queryset(self): qs = super().get_queryset(); return qs.select_related('cliente').prefetch_related(models.Prefetch('cuotas', queryset=DetalleCuotaCobro.objects.select_related('cuenta_bancaria_deposito').order_by('numero_cuota')))


class CobroDeleteView(FilteredByCompanyDeleteView):
    model = Cobro; template_name = 'gestion/cobro_confirm_delete.html'; success_url = reverse_lazy('gestion:cobro_list'); permission_required = 'gestion.delete_cobro'; success_message = "Cobro eliminado."

# --- CRUD Pagos (Refactorizado) ---
class PagoListView(FilteredByCompanyListView):
    model=Pago; template_name='gestion/pago_list.html'; context_object_name='pagos'; search_fields=['numero_documento', 'proveedor__nombre', 'grupo_concepto']
    def get_queryset(self): return super().get_queryset().select_related('proveedor','responsable_pago').order_by('-fecha_emision_factura')

class PagoDetailView(FilteredByCompanyDetailView):
    model=Pago; template_name='gestion/pago_detail.html'; context_object_name='pago'
    def get_queryset(self): return super().get_queryset().select_related('proveedor', 'responsable_pago', 'creado_por', 'actualizado_por').prefetch_related(models.Prefetch('cuotas_pago', queryset=DetalleCuotaPago.objects.order_by('numero_cuota')))

class PagoCreateView(FilteredByCompanyCreateView):
    model=Pago; form_class=PagoForm; template_name='gestion/pago_form.html'; success_url=reverse_lazy('gestion:pago_list'); permission_required='gestion.add_pago'

class PagoUpdateView(FilteredByCompanyUpdateView):
    model=Pago; form_class=PagoForm; template_name='gestion/pago_form.html'; success_url=reverse_lazy('gestion:pago_list'); permission_required='gestion.change_pago'
    CuotaPagoFormSet=inlineformset_factory(Pago, DetalleCuotaPago, form=DetalleCuotaPagoForm, extra=0, can_delete=False, fk_name='pago')
    # Sobrescribir get_context_data y form_valid para manejar formset (similar a CobroUpdateView)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs); prefix='cuotas_pago'
        if self.request.POST: ctx['cuota_formset'] = self.CuotaPagoFormSet(self.request.POST, instance=self.object, prefix=prefix)
        else: ctx['cuota_formset'] = self.CuotaPagoFormSet(instance=self.object, prefix=prefix)
        return ctx
    def form_valid(self, form):
        ctx = self.get_context_data(); cuota_formset = ctx['cuota_formset']
        if form.is_valid() and cuota_formset.is_valid():
            response = super().form_valid(form) # Guarda padre y pone mensaje
            cuota_formset.instance = self.object; cuota_formset.save()
            try: self.validar_suma_cuotas_pago(self.object)
            except ValidationError as e: messages.error(self.request,f"Error Validación: {e}"); return self.render_to_response(self.get_context_data(form=form,cuota_formset=cuota_formset))
            self.actualizar_estatus_pago(self.object);
            # messages.success(self.request,"Pago y cuotas actualizados.") # Mensaje ya puesto por mixin
            return response
        else:
             if not form.is_valid(): logger.warning(f"Errores PagoForm PK {self.object.pk}: {form.errors.as_json()}")
             if not cuota_formset.is_valid(): logger.warning(f"Errores CuotaPagoFormSet PK {self.object.pk}: {cuota_formset.errors}"); logger.warning(f"Non-form CuotaPagoFormSet errors: {cuota_formset.non_form_errors()}")
             messages.error(self.request,"Corrija los errores indicados.")
             return self.render_to_response(self.get_context_data(form=form,cuota_formset=cuota_formset))
    # Mantener helpers específicos
    def validar_suma_cuotas_pago(self, pago_instance): ...
    def actualizar_estatus_pago(self, pago_instance): ...
    def get_queryset(self): qs = super().get_queryset(); return qs.select_related('proveedor').prefetch_related('cuotas_pago')

class PagoDeleteView(FilteredByCompanyDeleteView):
    model=Pago; template_name='gestion/pago_confirm_delete.html'; success_url=reverse_lazy('gestion:pago_list'); permission_required='gestion.delete_pago'; success_message="Pago eliminado."

# --- CRUD Clientes (Refactorizado) ---
class ClienteListView(FilteredByCompanyListView):
     model=Cliente; template_name='gestion/cliente_list.html'; context_object_name='clientes'; search_fields=['identificacion', 'nombre', 'email', 'tags__name', 'contactos__nombre']
     def get_queryset(self): return super().get_queryset().prefetch_related('tags').order_by('nombre')

class ClienteDetailView(FilteredByCompanyDetailView):
     model=Cliente; template_name='gestion/cliente_detail.html'; context_object_name='cliente'
     def get_queryset(self): return super().get_queryset().prefetch_related('contactos', 'tags')

class ClienteCreateView(FilteredByCompanyCreateView):
     model=Cliente; form_class=ClienteForm; template_name='gestion/cliente_form.html'; success_url=reverse_lazy('gestion:cliente_list'); permission_required='gestion.add_cliente'

class ClienteUpdateView(FilteredByCompanyUpdateView):
     model=Cliente; form_class=ClienteForm; template_name='gestion/cliente_form.html'; success_url=reverse_lazy('gestion:cliente_list'); permission_required='gestion.change_cliente'
     ContactoFormSet=inlineformset_factory(Cliente, Contacto, form=ContactoForm, extra=1, can_delete=True, fk_name='cliente')
     def get_context_data(self, **kwargs): # Sobrescribir para añadir formset
          ctx=super().get_context_data(**kwargs); prefix='contactos'
          if self.request.POST: ctx['contacto_formset']=self.ContactoFormSet(self.request.POST,instance=self.object,prefix=prefix)
          else: ctx['contacto_formset']=self.ContactoFormSet(instance=self.object,prefix=prefix); return ctx
     def form_valid(self, form): # Sobrescribir para manejar formset
          ctx=self.get_context_data(); contacto_formset=ctx['contacto_formset']
          if form.is_valid() and contacto_formset.is_valid():
               response = super().form_valid(form) # Guarda padre y pone mensaje
               contacto_formset.instance=self.object; contacto_formset.save();
               # messages.success(self.request,"Cliente y contactos actualizados.") # Mensaje ya puesto
               return response
          else:
               if not contacto_formset.is_valid(): messages.error(self.request,"Corrija errores en contactos.")
               return self.render_to_response(self.get_context_data(form=form,contacto_formset=contacto_formset))
     def get_queryset(self): return super().get_queryset().prefetch_related('tags')

class ClienteDeleteView(FilteredByCompanyDeleteView):
     model=Cliente; template_name='gestion/cliente_confirm_delete.html'; success_url=reverse_lazy('gestion:cliente_list'); permission_required='gestion.delete_cliente'; success_message="Cliente eliminado."

# --- CRUD Proveedores (Refactorizado) ---
class ProveedorListView(FilteredByCompanyListView):
     model=Proveedor; template_name='gestion/proveedor_list.html'; context_object_name='proveedores'; search_fields=['identificacion', 'nombre', 'email', 'tags__name', 'contactos__nombre']
     def get_queryset(self): return super().get_queryset().prefetch_related('tags').order_by('nombre')

class ProveedorDetailView(FilteredByCompanyDetailView):
     model=Proveedor; template_name='gestion/proveedor_detail.html'; context_object_name='proveedor'
     def get_queryset(self): return super().get_queryset().prefetch_related('contactos', 'tags')

class ProveedorCreateView(FilteredByCompanyCreateView):
     model=Proveedor; form_class=ProveedorForm; template_name='gestion/proveedor_form.html'; success_url=reverse_lazy('gestion:proveedor_list'); permission_required='gestion.add_proveedor'

class ProveedorUpdateView(FilteredByCompanyUpdateView):
     model=Proveedor; form_class=ProveedorForm; template_name='gestion/proveedor_form.html'; success_url=reverse_lazy('gestion:proveedor_list'); permission_required='gestion.change_proveedor'
     ContactoFormSet=inlineformset_factory(Proveedor, Contacto, form=ContactoForm, extra=1, can_delete=True, fk_name='proveedor')
     def get_context_data(self, **kwargs): # Sobrescribir para añadir formset
          ctx=super().get_context_data(**kwargs); prefix='contactos_prov' # Prefijo diferente!
          if self.request.POST: ctx['contacto_formset']=self.ContactoFormSet(self.request.POST,instance=self.object,prefix=prefix)
          else: ctx['contacto_formset']=self.ContactoFormSet(instance=self.object,prefix=prefix); return ctx
     def form_valid(self, form): # Sobrescribir para manejar formset
          ctx=self.get_context_data(); contacto_formset=ctx['contacto_formset']
          if form.is_valid() and contacto_formset.is_valid():
               response = super().form_valid(form)
               contacto_formset.instance=self.object; contacto_formset.save();
               # messages.success(self.request,"Proveedor y contactos actualizados.")
               return response
          else:
               if not contacto_formset.is_valid(): messages.error(self.request,"Corrija errores en contactos.")
               return self.render_to_response(self.get_context_data(form=form,contacto_formset=contacto_formset))
     def get_queryset(self): return super().get_queryset().prefetch_related('tags')

class ProveedorDeleteView(FilteredByCompanyDeleteView):
     model=Proveedor; template_name='gestion/proveedor_confirm_delete.html'; success_url=reverse_lazy('gestion:proveedor_list'); permission_required='gestion.delete_proveedor'; success_message="Proveedor eliminado."

# --- CRUD Cuentas Bancarias (Refactorizado) ---
class CuentaBancariaListView(FilteredByCompanyListView):
     model=CuentaBancaria; template_name='gestion/cuenta_bancaria_list.html'; context_object_name='cuentas_bancarias'; search_fields = ['nombre_banco', 'numero_cuenta']
     def get_queryset(self): return super().get_queryset().select_related('actualizado_por').order_by('nombre_banco', 'numero_cuenta')

class CuentaBancariaCreateView(FilteredByCompanyCreateView):
     model=CuentaBancaria; form_class=CuentaBancariaForm; template_name='gestion/cuenta_bancaria_form.html'; success_url=reverse_lazy('gestion:cuenta_bancaria_list'); permission_required='gestion.add_cuentabancaria'

class CuentaBancariaUpdateView(FilteredByCompanyUpdateView):
     model=CuentaBancaria; form_class=CuentaBancariaForm; template_name='gestion/cuenta_bancaria_form.html'; success_url=reverse_lazy('gestion:cuenta_bancaria_list'); permission_required='gestion.change_cuentabancaria'

class CuentaBancariaDeleteView(FilteredByCompanyDeleteView):
     model=CuentaBancaria; template_name='gestion/cuenta_bancaria_confirm_delete.html'; success_url=reverse_lazy('gestion:cuenta_bancaria_list'); permission_required='gestion.delete_cuentabancaria'; success_message="Cuenta Bancaria eliminada."

# --- CRUD Gastos Recurrentes (Refactorizado) ---
class GastoRecurrenteListView(FilteredByCompanyListView):
     model=GastoRecurrente; template_name='gestion/gasto_recurrente_list.html'; context_object_name='gastos_recurrentes'; search_fields=['descripcion', 'grupo_concepto', 'responsable_pago__username']
     def get_queryset(self): return super().get_queryset().select_related('responsable_pago').order_by('grupo_concepto','descripcion')

class GastoRecurrenteDetailView(FilteredByCompanyDetailView):
     model = GastoRecurrente; template_name = 'gestion/gasto_recurrente_detail.html'; context_object_name = 'gasto'
     def get_queryset(self): return super().get_queryset().select_related('responsable_pago', 'creado_por', 'actualizado_por').prefetch_related('ocurrencias') # Incluir empresa via mixin
     def get_context_data(self, **kwargs): # Mantener lógica de próximas ocurrencias
        ctx=super().get_context_data(**kwargs); today=timezone.now().date(); prox_oc=None; err_oc=False
        try:
            if hasattr(self.object,'ocurrencias') and self.object.ocurrencias is not None: prox_oc=self.object.ocurrencias.filter(fecha_vencimiento__gte=today).order_by('fecha_vencimiento')[:5]
            else: logger.warning(f"GastoRecurrente {self.object.pk} sin 'ocurrencias'."); prox_oc=[]
        except Exception as e: logger.error(f"Error obteniendo ocurrencias para Gasto {self.object.pk}: {e}"); prox_oc=[]; err_oc=True
        ctx['proximas_ocurrencias']=prox_oc; ctx['error_cargando_ocurrencias']=err_oc; return ctx

class GastoRecurrenteCreateView(FilteredByCompanyCreateView):
     model=GastoRecurrente; form_class=GastoRecurrenteForm; template_name='gestion/gasto_recurrente_form.html'; success_url=reverse_lazy('gestion:gasto_recurrente_list'); permission_required='gestion.add_gastorecurrente'

class GastoRecurrenteUpdateView(FilteredByCompanyUpdateView):
     model=GastoRecurrente; form_class=GastoRecurrenteForm; template_name='gestion/gasto_recurrente_form.html'; success_url=reverse_lazy('gestion:gasto_recurrente_list'); permission_required='gestion.change_gastorecurrente'

class GastoRecurrenteDeleteView(FilteredByCompanyDeleteView):
     model=GastoRecurrente; template_name='gestion/gasto_recurrente_confirm_delete.html'; success_url=reverse_lazy('gestion:gasto_recurrente_list'); permission_required='gestion.delete_gastorecurrente'; success_message="Plantilla Gasto eliminada."

# --- Gestión Ocurrencias Gasto (Refactorizado) ---
class OcurrenciaGastoListView(FilteredByCompanyListView): # Usar Mixin base
     model=OcurrenciaGasto; template_name='gestion/ocurrencia_gasto_list.html'; context_object_name='ocurrencias'; paginate_by=20

     def get_queryset(self): # Sobrescribir para filtrar por campo relacionado y añadir filtros específicos
        try: empresa_id, _, _ = get_active_company_details(self.request)
        except PermissionDenied: return OcurrenciaGasto.objects.none()
        queryset = OcurrenciaGasto.objects.filter(gasto_recurrente__empresa_id=empresa_id).select_related('gasto_recurrente', 'pagado_por').order_by('-fecha_vencimiento')
        # Aplicar filtros GET
        filtros = self.request.GET; f_estatus=filtros.get('estatus'); q=filtros.get('q')
        if f_estatus and f_estatus in OcurrenciaGasto.EstatusOcurrencia.values: queryset=queryset.filter(estatus=f_estatus)
        f_fdesde=filtros.get('fecha_desde'); f_fhasta=filtros.get('fecha_hasta')
        try:
            if f_fdesde: queryset = queryset.filter(fecha_vencimiento__gte=date.fromisoformat(f_fdesde))
            if f_fhasta: queryset = queryset.filter(fecha_vencimiento__lte=date.fromisoformat(f_fhasta))
        except ValueError: pass # Ya se muestra warning en get_context_data si se necesita
        f_gid=filtros.get('gasto_recurrente_id');
        if f_gid and f_gid.isdigit(): queryset=queryset.filter(gasto_recurrente_id=int(f_gid))
        # Búsqueda genérica (adaptar campos si es necesario)
        search_fields = ['gasto_recurrente__descripcion', 'gasto_recurrente__grupo_concepto', 'gasto_recurrente__responsable_pago__username', 'comentarios']
        if q:
            q_objects = Q()
            for field in search_fields: q_objects |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(q_objects).distinct()
        return queryset

     def get_context_data(self, **kwargs): # Sobrescribir para añadir filtros específicos
        context = super().get_context_data(**kwargs) # Llama al mixin base
        # Añadir opciones para filtros
        context['estatus_choices'] = OcurrenciaGasto.EstatusOcurrencia.choices
        try: # Obtener solo gastos de la empresa activa
            context['gasto_recurrente_choices'] = GastoRecurrente.objects.filter(empresa_id=self.empresa_id, activo=True).order_by('descripcion')
        except PermissionDenied: # Si falla la obtención de empresa_id
             context['gasto_recurrente_choices'] = GastoRecurrente.objects.none()
        # Validar fechas aquí también para mostrar warning si es necesario
        f_fdesde=self.request.GET.get('fecha_desde'); f_fhasta=self.request.GET.get('fecha_hasta')
        try:
             if f_fdesde: date.fromisoformat(f_fdesde)
             if f_fhasta: date.fromisoformat(f_fhasta)
        except ValueError: messages.warning(self.request,"Formato de fecha inválido (usar YYYY-MM-DD).")
        return context

class OcurrenciaGastoUpdateView(FilteredByCompanyUpdateView): # Usar Mixin base
     model=OcurrenciaGasto; form_class=OcurrenciaGastoForm; template_name='gestion/ocurrencia_gasto_form.html';
     success_url=reverse_lazy('gestion:ocurrencia_gasto_list'); permission_required='gestion.change_ocurrenciagasto'

     # Sobrescribir get_queryset para filtrar por el padre (GastoRecurrente)
     def get_queryset(self):
          qs = super(UpdateView, self).get_queryset() # Llamar al de UpdateView directamente
          try: empresa_id, _, _ = get_active_company_details(self.request)
          except PermissionDenied: return OcurrenciaGasto.objects.none()
          return qs.filter(gasto_recurrente__empresa_id=empresa_id).select_related('gasto_recurrente', 'pagado_por')

     def get_context_data(self, **kwargs): # Añadir gasto_recurrente al contexto
         context = super().get_context_data(**kwargs)
         context['gasto_recurrente'] = self.object.gasto_recurrente # Añadir objeto padre
         return context

# --- CRUD Ventas Proyectadas (Refactorizado) ---
class VentaProyectadaListView(FilteredByCompanyListView):
    model=VentaProyectada; template_name='gestion/venta_proyectada_list.html'; context_object_name='ventas_proyectadas'; paginate_by=15; search_fields = ['codigo_oportunidad', 'cliente__nombre', 'descripcion', 'grupo_concepto', 'asesor_comercial__username']
    def get_queryset(self): return super().get_queryset().select_related('cliente','asesor_comercial').exclude(estatus=VentaProyectada.EstatusVenta.PERDIDA).order_by('fecha_cierre_estimada')

class VentaProyectadaDetailView(FilteredByCompanyDetailView):
    model=VentaProyectada; template_name='gestion/venta_proyectada_detail.html'; context_object_name='venta'
    def get_queryset(self): return super().get_queryset().select_related('cliente','asesor_comercial','responsable_seguimiento','creado_por','actualizado_por').prefetch_related('cobros_generados')

class VentaProyectadaCreateView(FilteredByCompanyCreateView):
    model=VentaProyectada; form_class=VentaProyectadaForm; template_name='gestion/venta_proyectada_form.html'; success_url=reverse_lazy('gestion:pipeline_ventas'); permission_required='gestion.add_ventaproyectada'

class VentaProyectadaUpdateView(FilteredByCompanyUpdateView):
    model=VentaProyectada; form_class=VentaProyectadaForm; template_name='gestion/venta_proyectada_form.html'; success_url=reverse_lazy('gestion:pipeline_ventas'); permission_required='gestion.change_ventaproyectada'

class VentaProyectadaDeleteView(FilteredByCompanyDeleteView):
    model=VentaProyectada; template_name='gestion/venta_proyectada_confirm_delete.html'; success_url=reverse_lazy('gestion:pipeline_ventas'); permission_required='gestion.delete_ventaproyectada'; success_message="Venta proyectada eliminada."

# --- Vistas de Lista Detallada de Cuotas (Refactorizadas) ---
class DetalleCuotaCobroListView(FilteredByCompanyListView): # Usar Mixin base
    model = DetalleCuotaCobro; template_name = 'gestion/detallecuotacobro_list.html'; context_object_name = 'cuotas_cobro'; paginate_by = 25
    # Sobrescribir get_queryset para filtrar por cobro__empresa_id y aplicar filtros específicos
    def get_queryset(self):
        try: empresa_id, _, _ = get_active_company_details(self.request)
        except PermissionDenied: return DetalleCuotaCobro.objects.none()
        # Usar el campo correcto para filtrar por empresa del padre
        queryset = DetalleCuotaCobro.objects.filter(cobro__empresa_id=empresa_id).select_related(
            'cobro', 'cobro__cliente', 'cuenta_bancaria_deposito'
        ).order_by('fecha_vencimiento', 'cobro__cliente__nombre')
        # Aplicar filtros específicos de esta vista
        filtros = self.request.GET; f_estatus = filtros.get('estatus', DetalleCuotaCobro.EstatusCuota.PENDIENTE); q = filtros.get('q')
        if f_estatus and f_estatus in DetalleCuotaCobro.EstatusCuota.values: queryset = queryset.filter(estatus=f_estatus)
        f_cliente = filtros.get('cliente_id');
        if f_cliente and f_cliente.isdigit(): queryset = queryset.filter(cobro__cliente_id=int(f_cliente))
        f_fdesde=filtros.get('fecha_desde'); f_fhasta=filtros.get('fecha_hasta')
        try:
            if f_fdesde: queryset = queryset.filter(fecha_vencimiento__gte=date.fromisoformat(f_fdesde))
            if f_fhasta: queryset = queryset.filter(fecha_vencimiento__lte=date.fromisoformat(f_fhasta))
        except ValueError: pass # Ya se muestra warning en context
        f_vencidas = filtros.get('vencidas');
        if f_vencidas == '1': queryset = queryset.filter(fecha_vencimiento__lt=timezone.now().date(), estatus=DetalleCuotaCobro.EstatusCuota.PENDIENTE)
        if q: queryset = queryset.filter(Q(cobro__numero_documento__icontains=q) | Q(cobro__cliente__nombre__icontains=q)).distinct()
        return queryset

    def get_context_data(self, **kwargs): # Sobrescribir para añadir filtros específicos
        context = super().get_context_data(**kwargs)
        context['estatus_choices'] = DetalleCuotaCobro.EstatusCuota.choices
        try: # Obtener solo clientes de la empresa activa
            context['cliente_choices'] = Cliente.objects.filter(empresa_id=self.empresa_id).order_by('nombre')
        except PermissionDenied: context['cliente_choices'] = Cliente.objects.none()
        # Validar fechas para warning
        f_fdesde=self.request.GET.get('fecha_desde'); f_fhasta=self.request.GET.get('fecha_hasta')
        try:
             if f_fdesde: date.fromisoformat(f_fdesde)
             if f_fhasta: date.fromisoformat(f_fhasta)
        except ValueError: messages.warning(self.request,"Formato fecha inválido (YYYY-MM-DD).")
        return context

class DetalleCuotaPagoListView(FilteredByCompanyListView): # Usar Mixin base
    model = DetalleCuotaPago; template_name = 'gestion/detallecuotapago_list.html'; context_object_name = 'cuotas_pago'; paginate_by = 25
    # Sobrescribir get_queryset para filtrar por pago__empresa_id y aplicar filtros
    def get_queryset(self):
        try: empresa_id, _, _ = get_active_company_details(self.request)
        except PermissionDenied: return DetalleCuotaPago.objects.none()
        queryset = DetalleCuotaPago.objects.filter(pago__empresa_id=empresa_id).select_related(
            'pago', 'pago__proveedor'
        ).order_by('fecha_vencimiento', 'pago__proveedor__nombre')
        # ... (Aplicar filtros f_estatus, f_proveedor, f_fechas, f_vencidas, query como antes) ...
        return queryset
     # Sobrescribir get_context_data para pasar filtros y choices
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estatus_choices'] = DetalleCuotaPago.EstatusCuotaPago.choices
        try: context['proveedor_choices'] = Proveedor.objects.filter(empresa_id=self.empresa_id).order_by('nombre')
        except PermissionDenied: context['proveedor_choices'] = Proveedor.objects.none()
        # ... (validación fechas) ...
        return context

# ============================================
# ===       REPORTES FINANCIEROS           ===
# ============================================

# --- Aging Report (Cuentas por Cobrar) ---
class AgingReportView(PlanFeatureRequiredMixin, FilteredByCompanyListView):
    model = DetalleCuotaCobro
    template_name = 'gestion/aging_report_cobrar.html'
    context_object_name = 'cuotas_vencidas_detalle'
    paginate_by = None

    permission_required = 'gestion.view_detallecuotacobro'
    feature_flag = 'permite_aging_report'
    search_fields = ['cobro__numero_documento', 'cobro__cliente__nombre']

    def get(self, request, *args, **kwargs):
        """
        Intercepta el parámetro `export` antes de renderizar plantilla.
        """
        self.object_list = self.get_queryset()
        export = request.GET.get('export', '').lower()

        # Calculamos el contexto completo (resumen + detalle)
        context = self.get_context_data()

        if export == 'csv':
            return self.export_csv(context)
        if export == 'pdf':
            return self.export_pdf(context)

        return super().get(request, *args, **kwargs)

    def export_csv(self, context):
        """
        Genera un CSV con el resumen de aging.
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="aging_report.csv"'

        writer = csv.writer(response)
        writer.writerow(['Rango (días)', 'Total Pendiente', 'Nº Cuotas'])
        for key, data in context['aging_data_summary'].items():
            if key == 'total_general':
                label = 'Total General'
            else:
                label = key.replace('_', '–')
            writer.writerow([label, f"{data['total']:.2f}", data['count']])

        return response

    def export_pdf(self, context):
        """
        Genera un PDF sencillo con el resumen de aging usando ReportLab.
        """
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, 800, f"Aging Report - {self.empresa_nombre}")
        p.setFont("Helvetica", 10)
        y = 770

        # Encabezados
        p.drawString(50, y, "Rango (días)")
        p.drawString(200, y, "Total Pendiente")
        p.drawString(350, y, "Nº Cuotas")
        y -= 20

        # Filas
        for key, data in context['aging_data_summary'].items():
            if key == 'total_general':
                label = 'Total General'
            else:
                label = key.replace('_', '–')
            p.drawString(50, y, label)
            p.drawRightString(300, y, f"{data['total']:.2f}")
            p.drawRightString(450, y, str(data['count']))
            y -= 15
            if y < 50:
                p.showPage()
                y = 800

        p.showPage()
        p.save()

        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')

    def get_queryset(self):
        qs = super().get_queryset()
        today = timezone.now().date()
        return (
            qs.filter(
                estatus=DetalleCuotaCobro.EstatusCuota.PENDIENTE,
                fecha_vencimiento__lt=today
            )
            .select_related('cobro', 'cobro__cliente', 'cobro__empresa')
            .order_by('cobro__cliente__nombre', 'fecha_vencimiento')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Reporte Antigüedad Saldos (Cobrar) - {self.empresa_nombre}"

        queryset = context.get('object_list', [])
        today = timezone.now().date()
        moneda_base = self.moneda_base

        # Resumen y detalle como antes
        aging_summary = OrderedDict([
            ('0_30', {'total': Decimal('0.00'), 'count': 0}),
            ('31_60', {'total': Decimal('0.00'), 'count': 0}),
            ('61_90', {'total': Decimal('0.00'), 'count': 0}),
            ('mas_90', {'total': Decimal('0.00'), 'count': 0}),
            ('total_general', {'total': Decimal('0.00'), 'count': 0}),
        ])
        aging_by_cliente = defaultdict(lambda: {
            'nombre': 'Desconocido',
            'rangos': OrderedDict([
                ('r0_30', Decimal('0.00')), ('r31_60', Decimal('0.00')),
                ('r61_90', Decimal('0.00')), ('r_mas_90', Decimal('0.00')),
                ('Total_Cliente', Decimal('0.00'))
            ]),
            'items': []
        })

        for cuota in queryset:
            if not cuota.fecha_vencimiento:
                continue
            dias = (today - cuota.fecha_vencimiento).days
            monto = cuota.monto_cuota or Decimal('0.00')
            monto_base = convertir_valor(monto, cuota.cobro.moneda, moneda_base, today)
            if monto_base is None:
                continue

            # Buckets
            if dias <= 30:
                br, bd = '0_30', 'r0_30'
            elif dias <= 60:
                br, bd = '31_60', 'r31_60'
            elif dias <= 90:
                br, bd = '61_90', 'r61_90'
            else:
                br, bd = 'mas_90', 'r_mas_90'

            aging_summary[br]['total'] += monto_base
            aging_summary[br]['count'] += 1
            aging_summary['total_general']['total'] += monto_base
            aging_summary['total_general']['count'] += 1

            cliente = cuota.cobro.cliente
            cid = cliente.pk if cliente else None
            aging_by_cliente[cid]['nombre'] = cliente.nombre if cliente else 'Desconocido'
            aging_by_cliente[cid]['rangos'][bd] += monto_base
            aging_by_cliente[cid]['rangos']['Total_Cliente'] += monto_base
            aging_by_cliente[cid]['items'].append(cuota)

        context['aging_data_summary'] = aging_summary
        context['aging_data_by_cliente'] = dict(
            sorted(aging_by_cliente.items(),
                   key=lambda i: i[1]['rangos']['Total_Cliente'],
                   reverse=True)
        )
        context['hoy'] = today
        return context


# --- Fin Vistas ---