import CAT24C256
import rtc_config
from reed_solomon import ReedSolomonSimple

class DatabaseManager:
    def __init__(self):
        """
        Valores inciales para la base de datos
        """
        self.eeprom = CAT24C256.EEPROMManager(0x50, 256, 1, 19, 18)
        self.max_pages = 256  # Total de páginas de la EEPROM
        self.gral_start_page = 0  # Primera página donde inician la informacion general
        self.admin_start_page = 1  # Primera página donde inician los datos del admin
        self.usr_start_page = 2  # Primera página donde inicia la informacion de usuarios
        self.tel_start_page = 7  # Primera página donde inicia los telefonos de los usuarios
        self.api_key_page = 10 # Página donde se almacenan las apikeys de los administradores
        self.log_start_page = 11  # Primera página donde inician los logs
        self.buffer = None
      
    def pad_data(self, data: str, length: int) -> str:
        data_bytes = data.encode('utf-8')
        if len(data_bytes) >= length:
            return data
        padded_data = data_bytes + b' ' * (length - len(data_bytes))
        return padded_data.decode('latin-1')
    
    def read_general_info(self):
        """
        Leer toda la informacion basica de la cerradura.
        """
        raw_data=self.eeprom.read(self.gral_start_page,1)
        self.depto_info=raw_data[0:10].decode("utf-8")
        print(f"Depto: {self.depto_info}")
        self.num_usr=int(raw_data[10:11].decode("utf-8"))
        print(f"Num Usuarios: {self.num_usr}")
        self.num_logs=int(raw_data[11:14].decode("utf-8"))
        print(f"Num Logs: {self.num_logs}")
        self.flags=raw_data[14:65]
        print(f"flags: {self.flags}")
        self.admins=int(raw_data[15:16].decode("utf-8"))
        print(f"Num Admins: {self.admins}")
        self.mst_key=raw_data[32:65]
        print(f"mst_key:{self.mst_key}")
    
    def update_gral_info(self):
        """
        Actualiza la informacion basica de la cerradura
        """
        str_num_logs = str(self.num_logs)
        while len(str_num_logs) < 3:
            str_num_logs = "0" + str_num_logs
        raw_data=(self.depto_info + str(self.num_usr) + str_num_logs + "1" + str(self.admins) + ("0" * 16)).encode() + self.mst_key
        self.eeprom.save(raw_data,self.gral_start_page,1)
        self.read_general_info()
    
    def save_general_info(self,depto_info,master_key):
        """
        Guarda la informacion basica de la cerradura
        
        Parameters:
        -depto_info:Nombre y Torre del depto
        -num_usr:Cuantos usuarios hay registrados
        -num_logs:Cuantos logs hay registrados
        -flags: Banderas que usaremos para modificar el comportamiento
        
        Returns:
        - None
        """
        self.depto_info=depto_info
        self.num_usr="0"
        self.num_logs="000"
        self.mst_key=master_key
        self.update_gral_info()
    
    def save_user_info(self, password, card, name):
        """
        Guarda la informacion de un usuario
        
        Parameters:
        -key: Contraseña de administrador
        -password:Contraseña del usuario
        -card:Identificador de tarjeta
        -name: Nombre del usuario
        
        Returns:
        - None
        """
        guard = [
            {'key': password, 'start': 0, 'end': 32}
        ]
        password = self.pad_data(password, 16)
        card = self.pad_data(card, 16)
        card_key = self.buffer
        del self.buffer
        data=password+card
        page = self.usr_start_page+self.num_usr
        self.eeprom.secure_save(guard,data,page)
        self.eeprom.partial_data(page, 32, card_key)
        self.save_api(name, page)
        self.num_usr += 1
        self.update_gral_info()
        del data
        
    def read_user_info(self, key, page):
        """
        Lee la informacion de un usuario
        
        Parameters:
        -key: Contraseña del usuario
        -page:Pagina que almacena los datos
        
        Returns:
        - None
        """
        guard = [
            {'key': key, 'start': 0, 'end': 32}
        ]
        raw_data=self.eeprom.secure_read(guard,page)
        self.usr_pswd = raw_data[0:15]
        self.usr_card = raw_data[16:32]
        raw_data=self.eeprom.read(page,1)
        self.usr_pswd_card = raw_data[33:48]
    
    #TODO Agregar is_user
    def is_user(self, key):
        """
        Verifica si es un usuario registrado
        
        Parameters:
        -key: Contraseña del usuario
        
        Returns:
        - None
        """
        try:
            for i in range(5):
                page = self.usr_start_page + i
                self.read_user_info(key, page)
                if self.usr_pswd:
                    self.usr_id_num = i
                    return True
            return False
        except Exception as e:
            return False
    
    #TODO Agregar is_admin
    def is_admin(self, key):
        """
        Verifica si es un usuario registrado
        
        Parameters:
        -key: Contraseña del usuario
        
        Returns:
        - None
        """
        data = self.read_admin_info(key)
        if data:
            return True
        return False
    
    def save_admin_pswd(self, key):
        """
        Guarda la contraseña de un administrador
        
        Parameters:
        -key: Contraseña del administrador
        
        Returns:
        - None
        """
        space = self.admins * 16
        guard = [
            {'key': key, 'start': space, 'end': space + 16}
        ]
        self.eeprom.secure_save(guard,key,self.admin_start_page,1)
        self.admins += 1
        self.update_gral_info()
        
        
    def read_admin_info(self, key):
        """
        Lee la informacion de un administrador
        
        Parameters:
        -key: Contraseña del administrador
        
        Returns:
        - None
        """
        guard = [
            {'key': key, 'start': 0, 'end': 48}
        ]
        raw_data=self.eeprom.secure_read(guard,self.admin_start_page)
        return raw_data
    
    def save_log(self, mensaje, tipo=1):
        """
        Registra un mensaje en un archivo de log con una marca de tiempo.
        
        Parameters:
        -key:La llave de encriptacion para los logs
        -data:El mensaje que se va a guardar
        -tipo:Que tipo de mensaje se va a guardar
        
        Returns:
        - None
        """
        print("Entrar a save_log")
        time = rtc_config.obtener_fecha_hora_rtc()
        data = f"{tipo}-{time}-{mensaje}"
        print(f"Tipo: {tipo} time: {time} Mensaje:{mensaje}")
        print(f"mst_key: {self.mst_key}")
        print(f"mst_key List: {list(self.mst_key)}")
        
        key=ReedSolomonSimple.pseudo_decrypt(list(self.mst_key))
        print(f"Key: {key}")
        guard = [
            {'key': key, 'start': 0, 'end': 64}
        ]
        log_page = self.log_start_page + self.num_logs
        print(f"Num Logs: {self.num_logs}")
        if log_page > self.max_pages:
            self.num_logs = 0
            log_page = self.log_start_page
        else:
            self.num_logs += 1
        print(f"Page: {log_page}")
        print(f"Num Logs: {self.num_logs}")
        print(f"Sentencia completa: Key~{key} Data~{data} page~{log_page}")
        self.eeprom.secure_save(guard,data,log_page)
        self.update_gral_info()
            
    def read_log(self, log_page):
        """
        Lee un solo log
        
        Parameters:
        -key: Contraseña del admin
        -page:Pagina que almacena el log
        
        Returns:
        - None
        """
        key=ReedSolomonSimple.pseudo_decrypt(list(self.mst_key))
        guard = [
            {'key': key, 'start': 0, 'end': 64}
        ]
        raw_data=self.eeprom.secure_read(guard,log_page)
        return raw_data

    def create_log_array(self, number=10, kindof = None):
        """
        Genera un reporte de logs que pueden clasificarse por tipo de log o solo el numero de logs
        que se deseen consultar
        
        Parameters:
        -key: Contraseña del administrador
        -kindof: Tipo de logs que se desea consultar (puede no ser ninguno)
        
        Returns:
        - Arreglo de logs que se encontro
        """
        print("Se creara un array de logs")
        print(f" Informacion recibida: Numero:{number} Tipo:{kindof}")
        log_array = []
        i = 0
        while len(log_array) <= number:
            num_log = self.log_start_page + self.num_logs - 1 - i
            
            if num_log < self.log_start_page or num_log >= self.max_pages:
                break
            
            log = self.read_log(num_log)
            print(f"Recuperado: {log}")
            if not log:
                    break
            
            if kindof:
                print(f"Log #{i}: log[0]-{log[0]} type:{type(log[0])}  log[0:1]-{log[0:1]} type:{type(log[0:1])}")
                if log[0] == str(kindof):
                    print("Anexado al array")
                    log_array.append(log)
            else:
                log_array.append(log)
            i += 1
        return log_array
    
    def save_phone(self, num_tel, admin=False):
        """
        Guarda un telefono de usuario sin encriptar 
        
        Parameters:
        -num_tel: Numero de telefono
        -admin: El telefono pertenece a un admin?
        
        Returns:
        - Arreglo de logs que se encontro
        """
        num_tel = self.pad_data(num_tel,8)
        buffer=ReedSolomonSimple.pseudo_encrypt(num_tel)
        num_seguro = bytes(buffer)
        page=self.tel_start_page
        if admin:
            offset = self.admins * 20
            if offset > 60:
                offset = 0
                page += 1
        else:
            page +=1
            if 0 <= self.num_usr < 1:
                offset = 20 * self.num_usr + 20
            elif 1 <= self.num_usr < 3:
                offset = -20 * x + 60
            else:
                page += 1
                if 3 <= self.num_usr < 4:
                    offset = 20 * self.num_usr - 60
                elif 4 <= self.num_usr <= 5:
                    offset = 20 * self.num_usr - 60
        print(f"Info Tel: page-{page}, offset-{offset},  num_seguro-{num_seguro}, len:{len(num_seguro)},")
        self.eeprom.partial_data(page, offset, num_seguro, 1)
    
    def get_api(self, admin=0):
        api=[]
        print("*°*°*° Empezando recuperacion de API *°*°*°")
        if admin == 1:
            print("Se requiere de los admin")
            data_str = self.eeprom.read(self.api_key_page, 1)
            print(f"Data: {data_str} len:{len(data_str)}")
            for i in range(0, len(data_str), 16):
                print(f"Segmento #{i}")
                segmento = data_str[i:i+16]
                print(f"Segmento: {segmento}")
                if segmento == b'0000000000000000':  # Verifica que el segmento no esté vacío
                    print("Segmento vacío detectado, saltando...")
                    continue
                
                print("Segmento no vacio")
                segmento = list(segmento)
                print(f"Segmento (list): {segmento}")
                plain_api=ReedSolomonSimple.pseudo_decrypt(segmento)
                print(f"API que se agrega: {plain_api}")
                api.append(plain_api[0:7])
        
        for page in range(self.usr_start_page, self.usr_start_page + 3):
            data_str = self.eeprom.read(page, 1)
            print(f"Data: {data_str} len:{len(data_str)}")
            data_str = data_str[48:64]
            print(f"Segmento: {data_str}")
            if data_str ==  b'0000000000000000':  # Verifica que el segmento no esté vacío
                print("Segmento vacío detectado, saltando...")
                continue
            data_str = list(data_str)
            print(f"Segmento (list): {data_str}")
            plain_api=ReedSolomonSimple.pseudo_decrypt(data_str)
            print(f"API que se agrega: {plain_api}")
            api.append(plain_api[0:7])
        
        return api
        
    def save_api(self, api, page):
        print("Comenzando Crypto")
        buffer=ReedSolomonSimple.pseudo_encrypt(api)
        print(f"Buffer: {buffer}")
        api_seguro = bytes(buffer)
        print(f"Guardando api: {api_seguro}")
        if page == self.api_key_page:
            offset = 16 * self.admins
        else:
            offset = 48
        print(f"offset: {offset}")
        self.eeprom.partial_data(page, offset, api_seguro, 1)
        
    #TODO agregar todo el iniciador de basa de datos de 0
    #def wipe_db():
        
    #TODO Verificar funcionamiento de recuperar Tel
    def read_phones(self):
        print(f"°°°Empezando a leer telefonos°°°")
        telefonos = []
        for page in range(self.tel_start_page, self.tel_start_page + 3):
            print(f"Pagina #{page}")
            data_str = self.eeprom.read(page,1)
            print(f"data_str: {data_str}")
            data_str = data_str[:-4]
            print(f"data recortada: {data_str}")
            for i in range(0, len(data_str), 20):
                print(f"Segmento #{i}")
                
                segmento = data_str[i:i+20]
                print(f"segmento: {segmento}")
                
                if segmento == b'00000000000000000000':
                    print("Segmento vacío detectado, saltando...")
                    continue
                
                segmento = segmento = [byte for byte in segmento]
                print(f"segmento (byte): {segmento}")
                
                if segmento:  # Verifica que el segmento no esté vacío
                    print(f"Segmento no vacio")
                    #segmento = list(segmento)
                    #print(f"Segmento rearmado: {segmento}")
                    plain_tel=ReedSolomonSimple.pseudo_decrypt(segmento)
                    print(f"Tel_recuperado: {plain_tel}")
                    telefonos.append(plain_tel)
                    print(f"Incluido en telefonos")
        return telefonos

    def delete_user(self, user_index):
        """
        Elimina un usuario específico y reorganiza los datos restantes.
    
        Parameters:
        - user_index: Índice del usuario que se desea eliminar (0 a num_usr - 1)
    
        Returns:
        - bool: True si la operación fue exitosa, False en caso de error.
        """
        try:
            # Validar que no se elimine al último usuario
            if self.num_usr <= 1:
                print("Debe haber al menos un usuario registrado. No se puede eliminar el último usuario.")
                return False

            # Validar índice del usuario
            if user_index < 0 or user_index >= self.num_usr:
                print("Índice de usuario inválido.")
                return False

            # Mover los datos de los usuarios posteriores hacia arriba
            for i in range(user_index, self.num_usr - 1):
                source_page = self.usr_start_page + i + 1
                target_page = self.usr_start_page + i
                # Leer los datos del siguiente usuario
                user_data = self.eeprom.read(source_page, 1)
                # Escribir los datos en la posición actual
                self.eeprom.save(user_data, target_page, 1)

            # Borrar los datos del último usuario
            last_page = self.usr_start_page + self.num_usr - 1
            self.eeprom.save(b'0' * 64, last_page, 1)  # 64 bytes de espacio vacío

            # Actualizar la información general
            self.num_usr -= 1
            self.update_gral_info()

            print(f"Usuario {user_index} eliminado y datos reorganizados.")
            return True

        except Exception as e:
            print(f"Error al eliminar usuario: {e}")
            return False

        