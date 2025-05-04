# gestion/management/commands/generar_ocurrencias.py

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from gestion.models import GastoRecurrente, OcurrenciaGasto
import logging

# Configurar un logger básico para este comando
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Genera las ocurrencias futuras de Gastos Recurrentes activos.'

    def add_arguments(self, parser):
        # Añadir argumento opcional para definir el horizonte en meses
        parser.add_argument(
            '--meses',
            type=int,
            default=3, # Generar para los próximos 3 meses por defecto
            help='Número de meses hacia adelante para generar ocurrencias (default: 3).',
        )
        parser.add_argument(
            '--forzar',
            action='store_true', # Si está presente, es True
            help='Forzar la generación incluso si ya existen ocurrencias (¡Usar con cuidado!). No recomendado para uso normal.',
        )

    def handle(self, *args, **options):
        meses_horizonte = options['meses']
        forzar_generacion = options['forzar']
        today = timezone.now().date()
        fecha_limite = today + relativedelta(months=meses_horizonte)

        self.stdout.write(f"Iniciando generación de ocurrencias de gastos hasta {fecha_limite.strftime('%Y-%m-%d')}...")

        gastos_activos = GastoRecurrente.objects.filter(activo=True)
        ocurrencias_creadas = 0
        ocurrencias_existentes = 0
        gastos_procesados = 0

        for gasto in gastos_activos:
            gastos_procesados += 1
            proxima_fecha = self.calcular_proxima_fecha(gasto.fecha_inicio, gasto.frecuencia, gasto.dia_del_mes)

            # Iterar generando fechas hasta alcanzar el horizonte o la fecha fin del gasto
            while proxima_fecha <= fecha_limite:
                # Saltar si la fecha es anterior a hoy (ya debería existir o haber pasado)
                if proxima_fecha < today:
                    proxima_fecha = self.calcular_proxima_fecha(proxima_fecha, gasto.frecuencia, gasto.dia_del_mes)
                    continue # Pasar a la siguiente iteración del while

                # Comprobar si el gasto tiene fecha fin y si la hemos superado
                if gasto.fecha_fin and proxima_fecha > gasto.fecha_fin:
                    break # No generar más para este gasto

                # --- Comprobación de existencia (Idempotencia) ---
                existe = OcurrenciaGasto.objects.filter(
                    gasto_recurrente=gasto,
                    fecha_vencimiento=proxima_fecha
                ).exists()

                if not existe or forzar_generacion:
                    if existe and forzar_generacion:
                         self.stdout.write(self.style.WARNING(f"Forzando regeneración para {gasto.descripcion} en {proxima_fecha} (ya existía)."))
                    try:
                        OcurrenciaGasto.objects.create(
                            gasto_recurrente=gasto,
                            fecha_vencimiento=proxima_fecha,
                            monto=gasto.monto_base, # Tomar el monto base de la plantilla
                            estatus=OcurrenciaGasto.EstatusOcurrencia.PENDIENTE,
                            # Otros campos como 'pagado_por' o 'comentarios' quedan vacíos por defecto
                        )
                        ocurrencias_creadas += 1
                        self.stdout.write(self.style.SUCCESS(f"  Creada ocurrencia para '{gasto.descripcion}' en {proxima_fecha}"))
                    except Exception as e:
                        logger.error(f"Error creando ocurrencia para {gasto.id} en fecha {proxima_fecha}: {e}")
                        self.stderr.write(self.style.ERROR(f"Error creando ocurrencia para {gasto.id} - {gasto.descripcion} en {proxima_fecha}"))
                else:
                    ocurrencias_existentes += 1
                    # self.stdout.write(f"  Ya existe ocurrencia para '{gasto.descripcion}' en {proxima_fecha}") # Opcional: hacerlo más verboso

                # Calcular la siguiente fecha para la próxima iteración del while
                proxima_fecha = self.calcular_proxima_fecha(proxima_fecha, gasto.frecuencia, gasto.dia_del_mes)

        self.stdout.write(self.style.SUCCESS(f"\nProceso completado."))
        self.stdout.write(f"Gastos recurrentes activos procesados: {gastos_procesados}")
        self.stdout.write(f"Nuevas ocurrencias generadas: {ocurrencias_creadas}")
        self.stdout.write(f"Ocurrencias que ya existían (omitidas): {ocurrencias_existentes}")


    def calcular_proxima_fecha(self, fecha_base, frecuencia, dia_mes=None):
        """
        Calcula la siguiente fecha de vencimiento basada en la frecuencia.
        Simplificado: Asume que fecha_base es la última fecha generada o la fecha de inicio.
        """
        if frecuencia == GastoRecurrente.FrecuenciaGasto.DIARIO:
            return fecha_base + timedelta(days=1)
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.SEMANAL:
            return fecha_base + timedelta(weeks=1)
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.QUINCENAL:
            return fecha_base + timedelta(days=15) # Simple: cada 15 días
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.MENSUAL:
            nueva_fecha = fecha_base + relativedelta(months=1)
            # Si se especificó un día y es válido para el mes, ajustarlo
            if dia_mes:
                try:
                    nueva_fecha = nueva_fecha.replace(day=dia_mes)
                except ValueError: # Día inválido para ese mes (ej: 31 en febrero)
                    # Ir al último día del mes anterior (aproximación)
                    # Una mejor lógica buscaría el último día del mes destino
                     nueva_fecha = (nueva_fecha.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
            return nueva_fecha
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.BIMESTRAL:
            return self.calcular_fecha_intervalo_meses(fecha_base, 2, dia_mes)
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.TRIMESTRAL:
            return self.calcular_fecha_intervalo_meses(fecha_base, 3, dia_mes)
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.SEMESTRAL:
             return self.calcular_fecha_intervalo_meses(fecha_base, 6, dia_mes)
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.ANUAL:
             return self.calcular_fecha_intervalo_meses(fecha_base, 12, dia_mes)
        elif frecuencia == GastoRecurrente.FrecuenciaGasto.UNICA_VEZ:
             # Para única vez, devolvemos una fecha muy lejana para que no entre en bucles
             return date.max
        else:
            # Frecuencia desconocida, no avanzar
            logger.warning(f"Frecuencia desconocida '{frecuencia}' encontrada.")
            return date.max # Evitar bucle infinito

    def calcular_fecha_intervalo_meses(self, fecha_base, meses, dia_mes=None):
        """Calcula fecha sumando N meses y ajustando el día si se especifica."""
        nueva_fecha = fecha_base + relativedelta(months=meses)
        if dia_mes:
             try:
                 nueva_fecha = nueva_fecha.replace(day=dia_mes)
             except ValueError:
                 nueva_fecha = (nueva_fecha.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return nueva_fecha