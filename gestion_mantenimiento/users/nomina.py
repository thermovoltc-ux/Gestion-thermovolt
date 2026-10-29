"""Motor de cálculo de nómina.

Funciones puras que convierten registros de asistencia, configuración de pago y
Descuentos en un desglose de salario para un técnico y un período.
"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

CERO = Decimal('0.00')
CIEN = Decimal('100')
HORA_NOCTURNA_INICIO = 19
MINUTOS_ALMUERZO = Decimal('30')


def _redondear(valor):
    """Redondea un valor decimal a dos decimales."""
    if valor is None:
        return CERO
    return Decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_horas_efectivas(fecha, hora_entrada, hora_salida):
    """Calcula horas efectivas, conservando el criterio anterior antes de su vigencia."""
    if not hora_entrada or not hora_salida:
        return None

    delta = hora_salida - hora_entrada
    horas_presencia = Decimal(delta.total_seconds()) / Decimal('3600')
    fecha_vigencia = date.fromisoformat(settings.NOMINA_FECHA_VIGENCIA_ALMUERZO)
    if fecha >= fecha_vigencia:
        horas_presencia = max(
            horas_presencia - MINUTOS_ALMUERZO / Decimal('60'),
            CERO,
        )
    return _redondear(horas_presencia)


def horas_trabajadas_en_registro(registro):
    """Devuelve las horas trabajadas de un RegistroAsistencia."""
    if registro.horas_trabajadas is not None:
        return _redondear(registro.horas_trabajadas)
    if registro.hora_entrada and registro.hora_salida:
        return calcular_horas_efectivas(
            registro.fecha,
            registro.hora_entrada,
            registro.hora_salida,
        )
    return CERO


def horas_nocturnas_en_registro(registro):
    """Calcula las horas trabajadas después de las 19:00."""
    if not registro.hora_entrada or not registro.hora_salida:
        return CERO

    entrada = registro.hora_entrada
    salida = registro.hora_salida

    if entrada.hour < HORA_NOCTURNA_INICIO:
        return CERO

    inicio_nocturno = entrada.replace(
        hour=HORA_NOCTURNA_INICIO,
        minute=0,
        second=0,
        microsecond=0,
    )
    if salida <= inicio_nocturno:
        return CERO

    inicio_real = max(entrada, inicio_nocturno)
    delta = salida - inicio_real
    return _redondear(Decimal(delta.total_seconds()) / Decimal('3600'))


def es_dia_festivo(fecha):
    """Verifica si una fecha es festiva; por ahora solo corresponde a domingo."""
    return fecha.weekday() == 6


def rango_quincena(fecha, corte):
    """Devuelve el corte y asigna el último día del mes al corte siguiente."""
    ultimo_dia = monthrange(fecha.year, fecha.month)[1]
    if corte == 'q1':
        ultimo_dia_mes_anterior = fecha.replace(day=1) - timedelta(days=1)
        return ultimo_dia_mes_anterior, fecha.replace(day=14)
    if corte == 'q2':
        return fecha.replace(day=15), fecha.replace(day=ultimo_dia - 1)
    raise ValueError(f'Corte quincenal inválido: {corte}')


def rango_quincena_actual(fecha):
    """Devuelve el rango predeterminado según la quincena actual."""
    corte = 'q1' if fecha.day <= 15 else 'q2'
    return rango_quincena(fecha, corte)


def calcular_periodo(usuario, fecha_inicio, fecha_fin):
    """Calcula el salario bruto, descuentos y neto de un técnico."""
    from .models import (
        CalendarioTecnico,
        ConfiguracionPago,
        Descuento,
        RegistroAsistencia,
    )

    try:
        config = usuario.configuracion_pago
    except ConfiguracionPago.DoesNotExist:
        config = None

    inicio_semana = fecha_inicio - timedelta(days=fecha_inicio.weekday())
    registros_semana = RegistroAsistencia.objects.filter(
        usuario=usuario,
        fecha__gte=inicio_semana,
        fecha__lte=fecha_fin,
    ).order_by('fecha')
    registros = [
        registro
        for registro in registros_semana
        if fecha_inicio <= registro.fecha <= fecha_fin
    ]
    dias_especiales = CalendarioTecnico.objects.filter(
        usuario=usuario,
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
    )
    dias_especiales_map = {dia.fecha: dia for dia in dias_especiales}

    horas_semana_estandar = (
        Decimal(config.horas_semana_estandar)
        if config
        else Decimal('42')
    )
    acumulado_por_semana = {}
    clasificacion_por_fecha = {}
    for registro in registros_semana:
        semana_inicio = registro.fecha - timedelta(days=registro.fecha.weekday())
        acumulado_previo = acumulado_por_semana.get(semana_inicio, CERO)
        horas = horas_trabajadas_en_registro(registro)
        acumulado_actual = acumulado_previo + horas
        extras = max(acumulado_actual - horas_semana_estandar, CERO) - max(
            acumulado_previo - horas_semana_estandar,
            CERO,
        )
        clasificacion_por_fecha[registro.fecha] = {
            'horas': horas,
            'normales': horas - extras,
            'extras': extras,
            'semana_provisional': (
                semana_inicio + timedelta(days=6) > fecha_fin
            ),
        }
        acumulado_por_semana[semana_inicio] = acumulado_actual

    horas_totales = CERO
    horas_normales = CERO
    horas_extras = CERO
    horas_nocturnas_total = CERO
    horas_festivas_total = CERO
    dias_trabajados = 0
    dias_descanso = 0
    detalle_dias = []

    for registro in registros:
        clasificacion = clasificacion_por_fecha[registro.fecha]
        horas = clasificacion['horas']
        normales = clasificacion['normales']
        extras = clasificacion['extras']
        nocturnas = horas_nocturnas_en_registro(registro)
        festivo = es_dia_festivo(registro.fecha)

        horas_totales += horas
        horas_normales += normales
        horas_extras += extras
        horas_nocturnas_total += nocturnas
        if festivo:
            horas_festivas_total += horas
        dias_trabajados += 1
        detalle_dias.append({
            'fecha': str(registro.fecha),
            'horas': float(horas),
            'horas_normales': float(normales),
            'horas_extras': float(extras),
            'nocturnas': float(nocturnas),
            'festivo': festivo,
            'semana_provisional': clasificacion['semana_provisional'],
        })

    for dia in dias_especiales_map.values():
        if dia.tipo == 'descanso':
            dias_descanso += 1

    horas_normales = _redondear(horas_normales)
    horas_extras = _redondear(horas_extras)
    dias_periodo = (fecha_fin - fecha_inicio).days + 1

    if config:
        valor_dia = Decimal(config.valor_dia or 0)
        valor_hora_normal = Decimal(config.valor_hora_normal or 0)
        valor_hora_extra = Decimal(config.valor_hora_extra or 0)
        recargo_nocturno_pct = Decimal(config.recargo_nocturno_porcentaje or 0)
        recargo_festivo_pct = Decimal(config.recargo_festivo_porcentaje or 0)
    else:
        valor_dia = CERO
        valor_hora_normal = CERO
        valor_hora_extra = CERO
        recargo_nocturno_pct = CERO
        recargo_festivo_pct = CERO

    if config and config.tipo_pago == 'por_dia':
        monto_base = valor_dia * Decimal(dias_trabajados)
    elif config and config.tipo_pago == 'salario_fijo':
        monto_base = _redondear(
            Decimal(config.salario_mensual or 0)
            * Decimal(dias_periodo)
            / Decimal('30')
        )
    else:
        monto_base = valor_hora_normal * horas_normales

    monto_extras = (
        valor_hora_extra * horas_extras
        if config and valor_hora_extra
        else CERO
    )
    monto_recargo_nocturno = CERO
    if (
        config
        and config.tipo_pago != 'por_dia'
        and valor_hora_normal
        and recargo_nocturno_pct
    ):
        monto_recargo_nocturno = (
            valor_hora_normal
            * horas_nocturnas_total
            * recargo_nocturno_pct
            / CIEN
        )

    monto_recargo_festivo = CERO
    if (
        config
        and config.tipo_pago != 'por_dia'
        and valor_hora_normal
        and recargo_festivo_pct
    ):
        monto_recargo_festivo = (
            valor_hora_normal
            * horas_festivas_total
            * recargo_festivo_pct
            / CIEN
        )

    bruto = _redondear(
        monto_base
        + monto_extras
        + monto_recargo_nocturno
        + monto_recargo_festivo
    )

    descuentos = Descuento.objects.filter(
        usuario=usuario,
        fecha_aplicacion__gte=fecha_inicio,
        fecha_aplicacion__lte=fecha_fin,
        activo=True,
    )
    total_descuentos = sum(
        (Decimal(descuento.monto) for descuento in descuentos),
        CERO,
    )
    neto = _redondear(bruto - total_descuentos)

    return {
        'horas_normales': _redondear(horas_normales),
        'horas_extras': _redondear(horas_extras),
        'horas_efectivas': _redondear(horas_totales),
        'horas_nocturnas': _redondear(horas_nocturnas_total),
        'horas_festivas': _redondear(horas_festivas_total),
        'dias_trabajados': dias_trabajados,
        'dias_descanso': dias_descanso,
        'bruto': bruto,
        'total_descuentos': _redondear(total_descuentos),
        'neto': neto,
        'detalles': {
            'config': (
                {
                    'tipo_pago': config.tipo_pago,
                    'valor_dia': float(valor_dia),
                    'valor_hora_normal': float(valor_hora_normal),
                    'valor_hora_extra': float(valor_hora_extra),
                }
                if config
                else None
            ),
            'monto_base': float(monto_base),
            'monto_extras': float(monto_extras),
            'monto_recargo_nocturno': float(monto_recargo_nocturno),
            'monto_recargo_festivo': float(monto_recargo_festivo),
            'dias': detalle_dias,
            'descuentos': [
                {
                    'tipo': descuento.tipo,
                    'monto': float(descuento.monto),
                    'descripcion': descuento.descripcion,
                }
                for descuento in descuentos
            ],
        },
    }
