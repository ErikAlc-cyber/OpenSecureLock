import mfrc522
from CAT24C256 import EEPROMManager
import keypad4x4
from ucryptolib import aes
import random
import time
import utime
from machine import Pin, PWM, I2C
from DatabaseManager import DatabaseManager as db
import rtc_config
from lcd_api import LcdApi
from pico_i2c_lcd import I2cLcd
from webserver import WiFiManager, WebServer
import uasyncio as asyncio
import sys
import network
import requests

MODE_CBC = 2
BLOCK_SIZE = 16
LCD_NUM_ROWS = 2
LCD_NUM_COLS = 16
LCD_ADDR = 0x27

# Configuracion de Hardware
BUZZER = PWM(Pin(21, mode=Pin.OUT))
BUZZER.freq(500)
OPEN_BTN = Pin(0, mode=Pin.IN, pull=Pin.PULL_DOWN)
DOOR_SENSOR = Pin(1, mode=Pin.IN, pull=Pin.PULL_DOWN)
IR_SENSOR = Pin(2, mode=Pin.IN, pull=Pin.PULL_DOWN)
DOOR_OUT = Pin(22, mode=Pin.OUT)

# Configuracion de la EEPROM
eeprom= EEPROMManager(0x50, 256, 1, 19, 18)
database = db()
database.read_general_info()

#Configuración LCD
i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=400000)
lcd = I2cLcd(i2c, LCD_ADDR, LCD_NUM_ROWS, LCD_NUM_COLS)
   
# Clase para inicializar la configuración
class setup_wizard:
    def __init__(self,newcode = False) -> None:
        self.newcode = newcode
        self.routes = [
            {
                '/': '/TT_pagina/Setupprincipal.html',
                '/edif': '/TT_pagina/Edificio.html',
                '/admin':'/TT_pagina/adminsetup.html',
                '/alta':'/TT_pagina/altasetup.html',
                '/config': '/TT_pagina/conectarsetup.html',
                '/styles':'/TT_pagina/styles.css',
            },
            {
                '/': '/TT_pagina/index.html',
                '/config': '/TT_pagina/conectarWifi.html',
                '/alta':'/TT_pagina/altaUsuario.html',
                '/baja':'/TT_pagina/bajaUsuario.html',
                '/cambio':'/TT_pagina/cambioUsuario.html',
                '/log':'/TT_pagina/logs.html',
                '/admin':'/TT_pagina/admin.html',
                '/styles':'/TT_pagina/styles.css',
            }]
        self.wifi_manager = WiFiManager(ssid="TT_2024-B037", password="12345678")
        prim_config = 1 if database.flags[0] == 49 else 0
        self.web_server = WebServer(self.wifi_manager, self.routes, prim_config)
    
    def no_config(self) -> None:
        """Genera una nueva contraseña aleatoria."""
        random_pwsd = [random.randint(0, 255) for _ in range(6)]
        self.newcode = True
        self.wifi_manager.start_ap()
        
    async def start(self):
        print("Iniciando servidor web en modo administración...")
        await self.web_server.start_server()

async def admin_mode(wizard):
    """Modo administración que inicia el servidor web."""
    wizard.no_config()
    await wizard.start()

# Clase para manejar tarjetas RFID
class RFIDCard:
    def __init__(self) -> None:
        self.uid = 0 # Identificador único de la tarjeta
        self.flag = False  # Indica si la tarjeta es válida
    
    def ReadData(self, block=8):
        """
        Lee los datos de la tarjeta RFID.
        
        :param block: Bloque de datos a leer (default: 8).
        :return: True si se leyó con éxito, False en caso contrario.
        """
        rdr = mfrc522.MFRC522(sck=6, miso=4, mosi=7, cs=5, rst=8)
        (stat, tag_type) = rdr.request(rdr.REQIDL)
        if stat == rdr.OK:
            (stat, raw_uid) = rdr.anticoll()
            if stat == rdr.OK:
                self.uid = "%02x%02x%02x%02x" % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3])
                if rdr.select_tag(raw_uid) == rdr.OK:
                    key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]  # Clave de autenticación
                    if rdr.auth(rdr.AUTHENT1A, block, key, raw_uid) == rdr.OK:
                        data = rdr.read(block)
                        self.flag = True
                        return self.flag
                    else:
                        print("AUTH ERR")
                else:
                    print("Failed to select tag")
        
        database.save_log("Tarjeta: No se pudo leer la tarjeta",3)
        
            
    def WriteData(self, databytes, block=8):
        """
        Escribe datos en la tarjeta RFID.
        
        :param databytes: Datos a escribir.
        :param block: Bloque donde se escribirán los datos (default: 8).
        :return: True si se escribió con éxito, False en caso contrario.
        """
        rdr = mfrc522.MFRC522(sck=6, miso=4, mosi=7, cs=5, rst=8)
        (stat, tag_type) = rdr.request(rdr.REQIDL)
        if stat == rdr.OK:
            (stat, raw_uid) = rdr.anticoll()
            if stat == rdr.OK:
                if rdr.select_tag(raw_uid) == rdr.OK:
                    key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF] # Clave de autenticación
                    if rdr.auth(rdr.AUTHENT1A, block, key, raw_uid) == rdr.OK:
                        stat = rdr.write(block, databytes)
                        rdr.stop_crypto1()
                        if stat == rdr.OK:
                            self.flag = False
                            database.save_log("Tarjeta: Se creo nueva contraseña de acceso",2)
                            return self.flag
                        else:
                            database.save_log("Tarjeta: No se pudo escribir",3)
                            print("FAILED")
                    else:
                        print("AUTH ERR")
                        database.save_log("Tarjeta: Error de autenticacion",3)
                else:
                    print("Failed to select tag")
                    database.save_log("Tarjeta: No se pudo leer la tarjeta",3)
        else:
            print("stat Failure")
            database.save_log("Tarjeta: error en stat",3)
        
        return self.flag
    
    def ban_uid(self):
        """Reinicia el UID y la bandera de estado."""
        self.uid = ""
        self.flag = False 

# Clase para manejar los sensores de la puerta
class Door_sensors:
    def __init__(self)->None:
        self.ir_flag = True
        self.door_flag = True
        
    def irq_ir(self, Pin):
        """
        Interrupción para el sensor infrarrojo.
        """
        if(self.ir_flag):
            print("IR Sensor Triggered")
            database.save_log("Sensor: Sensor infrarojo activado",2)
            #send_message(phone_number, api_key, "Se detecto un intento de entrada sospechoso en su domicilio")
        utime.sleep(0.3)
    
    def irq_door(self, Pin):
        """Interrupción para el sensor de la puerta."""
        print("Door Sensor Triggered")
        if(self.door_flag):
            print("Empezar a sonar buzzer")
            BUZZER.duty_u16(10000)
            database.save_log("Sensor: Sensor de puerta activado",2)
            #send_message(phone_number, api_key, "Se detecto un intento de entrada sospechoso en su domicilio")
        utime.sleep(0.3)
    
    def irq_open(self, Pin):
        """Interrupcion para abrir la puerta con el boton proporcionado"""
        print("Interrupcion de apertura de puerta")
        self.defuse_door()
        self.defuse_ir()
        print("Sensores desactivados")
        DOOR_OUT.toggle()
        print("Solenoide Activado")
        DOOR_OUT.toggle()
        print("Solenoide desactivado")
        
                
    def defuse_door(self):
        """Desactiva la alarma de la puerta."""
        self.door_flag = False 
    
    def defuse_ir(self):
        """Desactiva la alarma del sensor infrarrojo."""
        self.ir_flag = False
        
    def change_state(self):
        while DOOR_SENSOR.value() == 1:
            utime.sleep(0.05)
            self.defuse_ir()
            self.defuse_door()
            
        while DOOR_SENSOR.value() == 0:
            utime.sleep(0.05)
            
        self.activate_def()
        
    def activate_def(self):
        """Activa ambas alarmas."""
        self.door_flag = True
        self.ir_flag = True 

def url_encode(input_string):
    """
    Codifica una string en formato URL.
    :param input_string: La string a codificar.
    :return: La string codificada en formato URL.
    """
    # Mapa de caracteres permitidos en URL
    allowed_chars = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789"
        "-_.~"
    )
    
    encoded_string = ""
    for char in input_string:
        if char in allowed_chars:
            encoded_string += char
        else:
            encoded_string += f"%{ord(char):02X}"  # Convierte a hexadecimal
    
    return encoded_string

def send_message(phone_number, api_key, message, debug=0):
    """
    Envia un mensaje por WhatsApp.

    :param phone_number: Número al que se enviará el mensaje.
    :param api_key: Clave de la API para ese número.
    :param message: Mensaje que se enviará.
    :param debug: Saber si se requiere el modo depurado.
    :return: Valor booleano.
    """
    url = f'https://api.callmebot.com/whatsapp.php?phone=+521{phone_number}&text={message}&apikey={api_key}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            if debug == 1:
                print(f"Mensaje enviado a {phone_number}: {message}")
            database.save_log(f"Mensaje enviado", 2)
            return True
        else:
            if debug == 1:
                print(f"Fallo al enviar mensaje a {phone_number}: {response.text}")
            return False
    except Exception as e:
        error = f"Error enviando mensaje: {str(e)}"
        if debug == 1:
            print(error)
        database.save_log(error, 3)
        return False
        
def send_bulk_messages(message, admin_only=False, debug=0):
    """
    Envia mensajes a todos los números telefónicos recuperados.

    :param message: Mensaje que se enviará.
    :param admin_only: Indica si solo se debe enviar a números de administradores.
    :param debug: Saber si se requiere el modo depurado.
    """
    try:
        # Recuperar teléfonos y API keys
        print("*****Empezando mensajeria masiva*****")
        message = url_encode(message)
        phone_numbers = database.read_phones()
        #TODO Solucionar API
        admin=1 if admin_only else 0
        api_keys = database.get_api(admin)

        # Validar que haya datos suficientes
        if len(phone_numbers) != len(api_keys):
            raise ValueError("El número de teléfonos no coincide con el de claves API.")
        
        for phone, api in zip(phone_numbers, api_keys):
            if len(api) == 7:  # Verificar que la clave API tenga la longitud correcta
                send_message(phone, api, message, 1)
            else:
                error = f"Clave API inválida para {phone}: {api}"
                if debug:
                    print(error)
                database.save_log(error, 3)

    except Exception as e:
        error = f"Error al enviar mensajes masivos: {str(e)}"
        print(error)
        if debug:
            print(error)
        database.save_log(error, 3)
   
def lcd_str(text, row=0, col=0, delay=0.3):
    """
    Muestra texto en el LCD, desplazándolo si excede el límite de caracteres por fila.
    text: String que se desea mostrar.
    row: Fila donde se inicia la impresión del texto.
    col: Columna inicial para comenzar la impresión.
    delay: Tiempo de retraso entre cada desplazamiento si el texto es largo.
    """
    lcd.clear()  # Limpia la pantalla antes de mostrar el nuevo texto
    text += " "

    # Calcula el límite de caracteres por fila
    max_chars = LCD_NUM_COLS - col

    # Si el texto cabe en la pantalla, simplemente mostrarlo
    if len(text) <= max_chars + 1:
        lcd.move_to(col, row)
        lcd.putstr(text)
    else:
        # Si el texto excede el límite, mostrarlo en partes
        start = 0
        end = max_chars
        while True:
            # Calcula la ventana del texto para mostrar en pantalla
            end = start + max_chars
            lcd.move_to(col, row)
            if end <= len(text):
                lcd.putstr(text[start:end])
            else:
                # Si el final excede el largo del texto, envuelve al inicio
                lcd.putstr(text[start:] + text[:end - len(text)])

            time.sleep(1)  # Espera antes de desplazar

            # Avanza en el texto y envuelve si llega al final
            start = (start + 1) % len(text)

def random_shuffle(cadena, semilla=None):
    """
    Mezcla aleatoriamente los caracteres de una cadena.
    
    :param cadena: Cadena a mezclar.
    :param semilla: Semilla para la aleatoriedad.
    :return: Cadena mezclada.
    """
    if semilla is not None:
        urandom.seed(semilla)
    
    caracteres = list(cadena)
    longitud = len(caracteres)
    
    for i in range(longitud):
        indice_aleatorio = random.randint(0, longitud - 1)
        caracteres[i], caracteres[indice_aleatorio] = caracteres[indice_aleatorio], caracteres[i]
    
    cadena_mezclada = ''.join(caracteres)
    return cadena_mezclada

def bytes_random(length):
    """
    Genera bytes aleatorios.
    
    :param length: Longitud de los bytes aleatorios.
    :return: Bytes aleatorios.
    """
    random_bytes = bytes([random.randint(0, 255) for _ in range(length)])
    return random_bytes

def create_key(raw_uid):
    """
    Crea una clave AES a partir del UID de la tarjeta RFID.
    
    :param raw_uid: UID de la tarjeta.
    :return: Clave cifrada.
    """
    aes_key = bytes_random(16)
    iv = bytes_random(16)
    cipher = aes(aes_key, 2, iv)
    plaintext = random_shuffle(raw_uid)
    pad = 16 - len(plaintext) % 16
    plaintext = plaintext + " "*pad
    encrypted = iv + cipher.encrypt(plaintext)
    return encrypted

def pad_data(data: str, length: int) -> str:
    if len(data) >= length:
        return data
    padded_data = data + ' ' * (length - len(data))
    return padded_data

def main_loop(intentos):
    """Ciclo principal del programa."""
    utime.sleep(1)
    BUZZER.duty_u16(0) # Apaga el zumbador
    admin_flag = False
    stage_1 = True
    stage_2 = False
    while True:
        #inicio = time.ticks_ms()        
            
        # Manejo de intentos
        if intentos >= 3:
            database.save_log("Se detecto intento de entrada sospechoso",2)
            #TODO Agregar mensaje whats
            send_bulk_messages(f"{database.depto_info}: Se detecto intento de entrada sospechoso", 1)
            #send_message(phone_number, api_key, "Se detecto intento de entrada sospechoso en su domicilio")
            intentos = 0
            stage_1 = True
            stage_2 = False
                
        if stage_1:
                
            #Introducir codigo en le keypad
            print("")
            print("Introduce Contra")
            print("")
            lcd_str("Introduce Contra", 0,0)
    
            psk_code = ""
            intentos += 1
            # Ciclo para hacer display de la contraseña
            while True:
                key = keypad.Keypad4x4Read()
                if key is not None:
                    print(f"Tecla presionada: {key} type: {type(key)}")
                    
                    if key == "#":  # Fin de la entrada
                        break
                    elif key == "*":
                        psk_code = psk_code[:len(psk_code) - 1]
                    else:
                        psk_code += key  # Agrega la tecla a la cadena
                    
                    display = "*" * len(psk_code)
                    lcd_str(display, 0,0)
                utime.sleep(0.3)  # Espera un tiempo para evitar múltiples lecturas
            
            pwd = pad_data(psk_code, 16)
            print(f"Texto pad: {pwd} type: {type(pwd)}")
            
            #TODO Modificar a leer de la eeprom
            if database.is_admin(pwd):
                sensores.defuse_ir()
                sensores.defuse_door()
                intentos = 0
                admin_flag = True
                lcd_str("Admin",0,0)
                print("****Se salio de Admin****")
                prim_config = False if database.flags[0] == 49 else True
                if prim_config:
                    lcd_str("Modo admin", 0,0)
                    asyncio.run(admin_mode(wizard))
                    admin_flag = False
                    del pwd
                    break
                database.save_log("Se ingreso contraseña administrador",1)
                
            if database.is_user(pwd):
                intentos = 0
                database.save_log("Se ingreso contraseña",1)
                if admin_flag:
                    psk_code = ""
                    lcd_str("1 Web / 2 Abrir", 0,0)
                    
                    while True:
                        key = keypad.Keypad4x4Read()
                        if key is not None:
                            
                            if key == "1":  # Fin de la entrada
                                lcd_str("Modo admin", 0,0)
                                database.save_log("Se activo modo admin",1)
                                asyncio.run(admin_mode(wizard))
                                admin_flag = False
                                del pwd
                                break
                            
                            elif key == "2":
                                lcd_str("Autorizado", 0,0)
                                mensaje = "Acceso concedido con codigo"
                                database.save_log(mensaje,1)
                                #TODO Agregar mensaje whats
                                #send_bulk_messages("Acceso concedido", True, 1)
                                DOOR_OUT.toggle()
                                stage_1 = True
                                stage_2 = False
                                intentos = 0
                                #TODO Agregar funcion cambio de estado
                                #sensores.change_state()
                                time.sleep(2)
                                DOOR_OUT.toggle()
                                del pwd
                                break
                            else:
                                lcd_str("Incorrecto", 0,0)
                                utime.sleep(2)
                            
                    
                        utime.sleep(0.3)  # Espera un tiempo para evitar múltiples lecturas
                else:
                    stage_1 = False
                    stage_2 = True
            
            else:
                psk_code = None
            pass
                    
        if stage_2:
            print("")
            print("Acerca Tarjeta")
            print("")
            lcd_str("Acerca Tarjeta", 0,0)
            
            if CardObject.ReadData(12):
                #TODO Cambiar a leer de la eeprom
                print(f"Tarjeta actual: {pad_data(CardObject.uid, 16)} Tarjeta de usuario: {database.usr_card}")
                if (pad_data(CardObject.uid, 16) == database.usr_card):
                    print("Tarjeta Autorizada")
                    if CardObject.flag:
                        print(f"Tarjeta flag: {CardObject.flag}")
                        new_key=create_key(CardObject.uid)
                        print(f"Llave nueva: {new_key}")
                        if CardObject.WriteData(new_key, 12):
                            lcd_str("Error", 0,0)
                            mensaje = "Error en tarjeta"
                            database.save_log(mensaje,3)
                        else:
                            lcd_str("Autorizado", 0,0)
                            page = database.usr_start_page + database.usr_id_num
                            #TODO Agregar update a medias
                            eeprom.partial_data(page, 48, new_key[:16])
                            mensaje = "Acceso concedido a tarjeta"
                            database.save_log(mensaje,1)
                            #TODO Agregar mensaje whats
                            #send_bulk_messages("Acceso concedido")
                            DOOR_OUT.toggle()
                            stage_1 = True
                            stage_2 = False
                            intentos = 0
                            #TODO Agregar funcion cambio de estado
                            #sensores.change_state()
                            time.sleep(2)
                            DOOR_OUT.toggle()
                    else:
                        lcd_str("Bloqueado", 0,0)
                        print("Bloqueado")
                        database.save_log("Tarjeta: Mas de 3 intentos, bloquear",2)
                        intentos += 1
                else:
                    lcd_str("No autorizado", 0,0)
                    print("No autorizado")
                    database.save_log("Tarjeta: Tarjeta no autorizada",2)
                    intentos += 1
                    pass
                utime.sleep(1)        
            #print("Tiempo de ejecucion: ", time.ticks_diff(time.ticks_ms(), inicio), " ms")
            

if __name__=="__main__":
    CardObject = RFIDCard()
    sensores = Door_sensors()
    keypad = keypad4x4.Keypad4x4()
    wizard = setup_wizard()
    
    DOOR_SENSOR.irq(trigger=Pin.IRQ_RISING,handler=sensores.irq_door)
    IR_SENSOR.irq(trigger=Pin.IRQ_FALLING,handler=sensores.irq_ir)
    OPEN_BTN.irq(trigger=Pin.IRQ_RISING,handler=sensores.irq_open)

    try:
        intentos = 0
        main_loop(intentos)
 
    except Exception as e:
            print("'--- Caught Exception ---'")
            sys.print_exception(e)
            print("'--- End of Exception ---'")