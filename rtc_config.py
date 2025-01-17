import network
import ntptime
import machine
import utime
import time

# Conectar al WiFi
def conectar_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    while not wlan.isconnected():
        time.sleep(1)
    return wlan.isconnected()

# Ajustar la zona horaria a México (GMT-6, sin horario de verano)
def ajustar_zona_horaria():
    utc_offset = -6 * 3600  # UTC -6 horas para tiempo de Ciudad de México
    t = utime.time() + utc_offset
    tm = utime.localtime(t)
    return tm

# Sincronizar el reloj interno (RTC) con el servidor NTP
def sincronizar_hora():
    try:
        ntptime.host = 'pool.ntp.org'
        ntptime.settime()
        return True
    except Exception as e:
        print('Error al sincronizar la hora:', e)
        return False

# Inicializar el RTC con la hora actual ajustada
def inicializar_rtc():
    rtc = machine.RTC()
    tm = ajustar_zona_horaria()
    rtc.datetime((tm[0], tm[1], tm[2], 0, tm[3], tm[4], tm[5], 0))

# Formatear la fecha y hora para que sea legible
def formatear_fecha_hora(rtc_datetime):
    year, month, day, _, hour, minute, second, _ = rtc_datetime
    return f"{day:02d}-{month:02d}-{year} {hour:02d}:{minute:02d}:{second:02d}"

# Función principal de la biblioteca que devuelve el string de fecha y hora formateada
def obtener_fecha_hora_formateada(ssid, password):
    if conectar_wifi(ssid, password):
        if sincronizar_hora():
            inicializar_rtc()
            rtc = machine.RTC()
            fecha_hora = rtc.datetime()
            return formatear_fecha_hora(fecha_hora)
        else:
            return "Error: No se pudo sincronizar la hora con NTP"
    else:
        return "Error: No se pudo conectar al WiFi"

# Obtener fecha y hora directamente del RTC sin conectarse a Internet
def obtener_fecha_hora_rtc():
    rtc = machine.RTC()
    fecha_hora = rtc.datetime()
    return formatear_fecha_hora(fecha_hora)
