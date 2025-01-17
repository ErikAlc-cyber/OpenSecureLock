import network
import socket
import ure
import time
import utime
import uasyncio as asyncio
from machine import Pin
import mfrc522
from ucryptolib import aes
import random
from DatabaseManager import DatabaseManager as db
from reed_solomon import ReedSolomonSimple as RS
import rtc_config

class NFCReader:
    def __init__(self):
        # Inicializa el lector MFRC522 solo una vez
        self.rdr = mfrc522.MFRC522(sck=6, miso=4, mosi=7, cs=5, rst=8)
    
    def random_shuffle(self, cadena, semilla=None):
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

    def bytes_random(self, length):
        """
        Genera bytes aleatorios.
    
        :param length: Longitud de los bytes aleatorios.
        :return: Bytes aleatorios.
        """
        random_bytes = bytes([random.randint(0, 126) for _ in range(length)])
        return random_bytes
    
    def create_key(self, raw_uid):
        """
        Crea una clave AES a partir del UID de la tarjeta RFID.
    
        :param raw_uid: UID de la tarjeta.
        :return: Clave cifrada.
        """
        aes_key = self.bytes_random(16)
        iv = self.bytes_random(16)
        cipher = aes(aes_key, 2, iv)
        plaintext = self.random_shuffle(raw_uid)
        pad = 16 - len(plaintext) % 16
        plaintext = plaintext + " "*pad
        encrypted = iv + cipher.encrypt(plaintext)
        return encrypted
    
    def WriteData(self, databytes, block=8):
        """
        Escribe datos en la tarjeta RFID.
        
        :param databytes: Datos a escribir.
        :param block: Bloque donde se escribirán los datos (default: 8).
        :return: True si se escribió con éxito, False en caso contrario.
        """
        self.rdr = mfrc522.MFRC522(sck=6, miso=4, mosi=7, cs=5, rst=8)
        (stat, tag_type) = self.rdr.request(self.rdr.REQIDL)
        if stat == self.rdr.OK:
            (stat, raw_uid) = self.rdr.anticoll()
            if stat == self.rdr.OK:
                if self.rdr.select_tag(raw_uid) == self.rdr.OK:
                    key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]  # Clave de autenticación
                    if self.rdr.auth(self.rdr.AUTHENT1A, 12, key, raw_uid) == self.rdr.OK:
                        stat = self.rdr.write(12, databytes)
                        self.rdr.stop_crypto1()
                        if stat == self.rdr.OK:
                            return True
                        else:
                            print("FAILED")
                else:
                    print("Failed to select tag")
        print("")
        return False

    def ReadData(self, block=8):
        """
        Lee los datos de la tarjeta RFID.
        
        """
        (stat, tag_type) = self.rdr.request(self.rdr.REQIDL)
        if stat == self.rdr.OK:
            (stat, raw_uid) = self.rdr.anticoll()
            if stat == self.rdr.OK:
                uid = "%02x%02x%02x%02x" % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3])
                if self.rdr.select_tag(raw_uid) == self.rdr.OK:
                    key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]  # Clave de autenticación
                    if self.rdr.auth(self.rdr.AUTHENT1A, block, key, raw_uid) == self.rdr.OK:
                        return uid
                    else:
                        print("AUTH ERR")
                else:
                    print("Failed to select tag")

nfc = NFCReader()

class WiFiManager:
    
    def __init__(self, ssid="PicoW_AP", password="12345678"):
        self.ssid = ssid
        self.password = password
        self.ap = network.WLAN(network.AP_IF)
        self.timeout = 3 * 60

    def start_ap(self):
        print("Iniciando AP...")
        self.ap.config(essid=self.ssid, password=self.password)
        self.ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
        self.ap.active(True)
        
        while not self.ap.active():
            print("Esperando a que AP esté activo...")
            time.sleep(1)
            
        
        print("Red WiFi creada:")
        print(f"SSID: {self.ssid}")
        print(f"Contraseña: {self.password}")
        print("Configuración de red AP:", self.ap.ifconfig())
        return self.ap

    def scan_wifi(self):
        print("Escaneando redes WiFi cercanas...")
        networks = []
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        access_points = sta.scan()
        print(f"Redes encontradas: {len(access_points)}")
        
        for ap in access_points:
            ssid = ap[0].decode('UTF-8')
            rssi = ap[3]
            if ssid and ssid != " ":
                networks.append(ssid)
                print(f"SSID: {ssid}, RSSI: {rssi}")
           
        sta.active(False)
        return networks

    def connect_to_wifi(self, ssid, password):
        print(f"Conectando a la red WiFi: {ssid}...")
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.connect(ssid, password)

        for _ in range(10):
            if sta.isconnected():
                print("Conectado a la red WiFi.")
                try:
                    rtc_config.obtener_fecha_hora_formateada(ssid, password)
                except Exception as e:
                    print(f"No se configuro rtc, error: {e}")
                    pass 
                return True
            time.sleep(1)
        
        print("Error al conectar a la red WiFi.")
        return False

    def stop_ap(self):
        self.ap.active(False)
    
    def check_clients(self):
        stations = self.ap.status('stations')
        return len(stations) > 0

class WebServer:

    def __init__(self, wifi_manager, routes, modo_setup):
        self.wifi_manager = wifi_manager
        self.routes_map = routes[modo_setup]
        self.db=db()
        self.db.read_general_info()
        self.server_socket = None
        self.continue_flag = True
    
    def url_get(self, request, parametro):
        print("Entrar a url_get")
        patron = parametro + r'=([^&]+)'
        print(f"Patron: {patron}")
        resultado = ure.search(patron, request)
        print(f"Resultado: {resultado}")
        if resultado:
            valor = resultado.group(1)
            return self.url_decode(valor)
        return None

    def pad_data(self, data: str, length: int) -> str:
        data_bytes = data.encode('utf-8')
        if len(data_bytes) >= length:
            return data
        padded_data = data_bytes + b' ' * (length - len(data_bytes))
        print(f"Padded Data: {padded_data}")
        return padded_data.decode('latin-1')

    async def handle_request(self, client_socket):
        try:
            prim_config = 1 if self.db.flags[0] == 49 else 0
            request = client_socket.recv(1024).decode('utf-8')
            route_get = ure.search(r"GET (/[^ ]*)", request)
            route_post = ure.search(r"POST (/[^ ]*)", request)

            if route_get:
                path = route_get.group(1).split("?", 1)[0]
                print(f"Solicitud GET: {path}")
                if path in self.routes_map:
                    html_template = self.load_html_template(self.routes_map[path])
                    if path == '/config':
                        networks = self.wifi_manager.scan_wifi()
                        response = self.generate_web_page(html_template, networks)
                    
                    #TODO Agregar cosas de logs
                    elif path == '/' and prim_config == 1:
                        print(f"Se entro a /")
                        log = self.db.create_log_array(number=10, kindof = None)
                        print(f"Se creo el array: {log}")
                        response = self.generate_web_page(html_template, log=log)
                    
                    elif path == '/log':
                        print(f"Request: {route_get.group(1)}")
                        print(f"Request split: {route_get.group(1).split("?", 1)[1]}")
                        req_split = route_get.group(1).split("?", 1)[1]
                        log_type = self.url_get(req_split,'type')
                        print(f"Log type: {type}")
                        log = self.db.create_log_array(number=10,kindof = log_type)
                        print(f"Log Array: {log}")
                        response = self.generate_web_page(html_template, log=log)
                    
                    elif path == '/baja':
                        print(f"Request: {route_get.group(1)}")
                        api = self.db.get_api()
                        print(f"API Array: {api}")
                        response = self.generate_web_page(html_template, api=api)
                        
                    else:
                        response = html_template
                elif "GET /exit" in request:
                    self.continue_flag = False
                    response = "<html><body><h1>Configuracion Guardada, puede cerrar esta pantalla</h1></body></html>"
                else:
                    response = "<html><body><h1>Error 404: Ruta no encontrada</h1></body></html>"

            elif route_post:
                print(f"Solicitud POST: {request}")
                path = route_post.group(1)
                
                if path == "/connect":
                    ssid = self.url_get(request,'ssid')
                    password = self.url_get(request,'password')
                    if self.wifi_manager.connect_to_wifi(ssid, password):
                        response = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "success", "message": "Conexión éxitosa"}'
                
                elif path == "/edif":
                    torre = self.url_get(request,'torre')
                    numdep = self.url_get(request,'numdep')
                    dat_depto = self.pad_data(f"{torre}-{numdep}",10)
                    key = nfc.bytes_random(16)
                    raw_key = RS.pseudo_encrypt(key)
                    raw_key = bytes(raw_key)
                    self.db.save_general_info(dat_depto, raw_key)
                    response = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "success", "message": "Configuracion incial exitosa"}'
                
                elif path == "/admin":
                    phone = self.url_get(request, 'phone')
                    password = self.url_get(request,'password')
                    password = self.pad_data(password, 16)
                    apikey = self.url_get(request,'apikey')
                    self.db.save_phone(phone, True)
                    self.db.save_api(apikey, 10)
                    self.db.save_admin_pswd(password)
                    response = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "success", "message": "Alta de admin realizada con éxito."}'
            
                elif path == "/nfc-scan":
                    uid = nfc.ReadData()
                    card_key=nfc.create_key(uid)
                    if nfc.WriteData(card_key,12):
                        self.db.buffer = bytearray(card_key)[:16]
                    response = 'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n{"uid": "' + str(uid) + '"}'
                    
                elif path == "/alta":
                    phone = self.url_get(request, 'phone')
                    password = self.url_get(request,'password')
                    password = self.pad_data(password,16)
                    self.db.save_phone(phone)
                    apikey = self.url_get(request,'apikey')
                    uid = self.url_get(request,'uid')
                    uid = self.pad_data(uid,16)
                    self.db.save_user_info(password, uid, apikey)
                    response = 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "success", "message": "Alta de usuario realizada con éxito."}'
            
            else:
                response = self.http_response(400, "Bad Request")
            
            client_socket.send(response)

        except Exception as e:
            print(f"Error al manejar la solicitud: {e}")
            client_socket.send(self.http_response(500, "Internal Server Error"))

        finally:
            await asyncio.sleep(0)  # Cede el control para otras tareas
            client_socket.close()  # Asegurar que el socket siempre se cierra

    def load_html_template(self, file_path):
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except OSError:
            return "<html><body><h1>Error 404: Archivo no encontrado</h1></body></html>"

    def generate_web_page(self, html, networks=None, api=None, log=None):
        """Reemplaza los marcadores {{}} en la plantilla HTML si existe"""
        # Procesar los logs
        if log is not None:
            if not log:  # Si log está vacío
                log_array = "<tr><td>No hay registros aun</td></tr>"
            else:  # Si log contiene datos
                log_array = "".join([f"<tr><td>{logs}</td></tr>" for logs in log])
            html = html.replace("{{LOG_LIST}}", log_array)
    
        # Procesar las redes WiFi
        if networks is not None:
            if not networks:  # Si networks está vacío
                ssid_options = "<option value='0'>No hay redes disponibles</option>"
            else:  # Si networks contiene datos
                ssid_options = "".join([f"<option value='{net}'>{net}</option>" for net in networks])
            html = html.replace("{{SSID_LIST}}", ssid_options)
    
        # Procesar los usuarios de la API
        if api is not None:
            if not api:  # Si api está vacío
                api_array = "<option value='0'>No hay usuarios registrados</option>"
            else:  # Si api contiene datos
                api_array = "".join([f"<option value='{index}'>{user}</option>" for index, user in enumerate(api)])
            html = html.replace("{{USER_LIST}}", api_array)
    
        return html

    def url_decode(self, url_string):
        hex_to_char = lambda h: chr(int(h, 16))
        result = ""
        i = 0
        while i < len(url_string):
            if url_string[i] == '%':
                result += hex_to_char(url_string[i+1:i+3])
                i += 3
            else:
                result += url_string[i]
                i += 1
        return result
    
    def kill_webserver(self):
        self.server_socket.close()
        print("Servidor cerrado")

    def http_response(self, status_code, content):
        status_messages = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}
        return f"HTTP/1.1 {status_code} {status_messages.get(status_code, '')}\\r\\nConnection: close\\n\\n\\r\\n{content}"

    async def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', 80))
        self.server_socket.listen(5)
        start_time = utime.time()
        print("Servidor web iniciado, esperando conexiones...")

        while self.continue_flag:
            if self.wifi_manager.check_clients():
                client_socket, addr = self.server_socket.accept()
                #print(f"Conexión desde {addr[0]}")
                await self.handle_request(client_socket)
            elif (utime.time() - start_time >= self.wifi_manager.timeout) :
                    self.continue_flag = False
                    
        self.server_socket.close()
        print("Servidor cerrado")
        self.wifi_manager.stop_ap()
        print("AP finalizado")