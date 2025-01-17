from machine import I2C, Pin
import re
import cryptolib
import ujson
import time

class CAT24C256(object):

    def __init__(self, i2c, i2c_addr, pages=512, bpp=64):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.pages = pages
        self.bpp = bpp # bytes per page

    def capacity(self):
        """Capacidad de almacenamiento en bytes"""
        return self.pages * self.bpp

    def read(self, addr, nbytes):
        """Leer uno o mas bytes the la eeprom EEPROM empezando por una direccion especifica"""
        return self.i2c.readfrom_mem(self.i2c_addr, addr, nbytes, addrsize=16)

    def write(self, addr, buf):
        """Escribir uno o mas bytes the la eeprom EEPROM empezando por una direccion especifica"""
        offset = addr % self.bpp
        partial = 0
        
        # partial page write
        if offset > 0:
            partial = self.bpp - offset
            self.i2c.writeto_mem(self.i2c_addr, addr, buf[0:partial], addrsize=16)
            time.sleep_ms(5)
            addr += partial
        
        # full page write
        for i in range(partial, len(buf), self.bpp):
            self.i2c.writeto_mem(self.i2c_addr, addr+i-partial, buf[i:i+self.bpp], addrsize=16)
            time.sleep_ms(5)
    
    def wipe(self):
        """Borra toda la eeprom"""
        buf = b'0' * self.bpp
        for i in range(self.pages):
            self.write(i*self.bpp, buf)


class EEPROMManager:
    """
    Clase para manejar la EEPROM con funciones de cifrado y descifrado.
    """

    def __init__(self, addr, size, i2c_number, pin_scl, pin_sda):
        """
        Inicializa el objeto EEPROMManager.
        """
        self.I2C_ADDR = addr
        self.EEPROM_SIZE = size
        self.i2c = I2C(i2c_number, scl=Pin(pin_scl), sda=Pin(pin_sda), freq=800000)
        self.control = CAT24C256(self.i2c,self.I2C_ADDR)
    
    def wipe_all(self):
        self.control.wipe()

    def pad_block(self, block, block_size=16, pad_byte=b' '):
        """
        Rellena un bloque de datos hasta block_size bytes con el byte dado.
        Por defecto, el byte de relleno es el espacio en blanco (0x20).
        """
        if not isinstance(block, bytes):
            raise TypeError(f"Se esperaba un objeto de tipo 'bytes', pero se recibió {type(block)}")
        
        padding_needed = block_size - len(block)
        if padding_needed > 0:
            block += pad_byte * padding_needed
        return block
    
    def partial_data(self, page, offset, data, debug = 0):
        """
        Actualiza parte de la pagina en la EEPROM sin reescribir la pagina.
        Parameters:
        - page: Numero de pagina a actualizar.
        - offset: El byte de inicio donde comenzar a sobreescribir.
        - data: Los nuevos datos a escribir (No exceder 64 bytes - offset bytes).
        - key: Llave de encriptacion.
    
        Returns:
        - None
        """
         # Verificar el tipo de data antes de procesar
        if debug == 1:
            print(f"Tipo de data: {type(data)}")
            print(f"Localizacion: pag-{page} pad-{offset}")
            print(f"Contenido de data: {data}")
        
        if isinstance(data, (bytearray)):
            data = bytes(data)

        data_length = len(data)
        if debug == 1:
            print(f"Longitud de data: {data_length}")

        if offset + data_length > 64:
            print(f"len bytes: {offset + data_length}")
            raise ValueError("Datos exceden el limite de bytes")

        current_data = self.read(page, 1)
        if debug == 1:
            print(f"PD: Data-{data}")
            print(f"current data: {current_data}")
        
        updated_data = bytearray(current_data) 
        if debug == 1:
            print(f"byte data: {updated_data}")
    
        updated_data[offset:offset + data_length] = data
        updated_data = bytes(updated_data)
        if debug == 1:
            print(f"Updated data: {updated_data}")
        
        print("Entrando a funcion self.save")
        self.save(updated_data, page)

    def secure_save(self, keys, data, page, debug=0):
        """
        Guarda datos de manera segura en la EEPROM utilizando cifrado AES.
        Permite el uso de diferentes llaves para diferentes segmentos de datos.
        
        keys: Lista de diccionarios que contienen:
            - 'key': la llave de encriptación
            - 'start': índice de inicio de datos para esta llave
            - 'end': índice de fin de datos para esta llave
        """
        data = bytes(data, 'utf-8')
        
        
        if debug == 1:
            print(f"Datos a guardar: {data}")
            
        encrypted_buffer = b''
        
        for segment in keys:
            key = segment['key']
            start = segment['start']
            end = segment['end']
        
            if isinstance(key, str):  # Si la clave es una cadena, conviértela a bytes
                key = key.encode('utf-8')
        
            aes = cryptolib.aes(key, 1)
            segment_data = data[start:end]
            encrypted_data = bytearray()
            
            for i in range(0, len(segment_data), 16):
                block = segment_data[i:i + 16]
                if len(block) < 16:
                    block += b'\x00' * (16 - len(block))
                encrypted_data.extend(aes.encrypt(block))
            segment_offset = start % self.control.bpp
            
        if debug == 1:
             print(f"Guardando en la pagina {page}, desde el offset {segment_offset} datos encriptados: {encrypted_data}")
        
        self.partial_data(page, segment_offset, encrypted_data, debug)

    def secure_read(self, keys, page, debug=0):
        """
        Lee datos de manera segura desde la EEPROM utilizando descifrado AES.
        Permite el uso de diferentes llaves para diferentes segmentos de datos.
    
        keys: Lista de diccionarios que contienen:
            - 'key': la llave de desencriptación
            - 'start': índice de inicio en la página para este segmento
            - 'end': índice de fin en la página para este segmento
        """
        page_address = page * 64
        decrypted_data = b''

        for segment in keys:
            key = segment['key']
            start = segment['start']
            end = segment['end']
        
            if isinstance(key, str):  # Si la clave es una cadena, conviértela a bytes
                key = key.encode('utf-8')
        
            # Inicialización del cifrado AES en modo ECB
            aes_decrypt = cryptolib.aes(key, 1)  # 1 representa el modo ECB
            segment_data = b''
        
            for i in range(start, end, 16):  # Leer en bloques de 16 bytes
                try:
                    encrypted_read = self.control.read(page_address + i, 16)  # Leer 16 bytes desde la EEPROM
                    decrypted_block = aes_decrypt.decrypt(encrypted_read)  # Descifrar el bloque
                    try:
                        decrypted_block.decode('utf-8')  # Intentar decodificar el bloque
                        segment_data += decrypted_block  # Agregar solo si la decodificación es exitosa
                    except:
                        if debug == 1:
                            print(f"Bloque descifrado contiene datos no válidos: {decrypted_block}")
                        pass
        
                except Exception as e:
                    if debug == 1:
                        print(f"Error al leer segmento: {e}")
                    break
        
            # Agregar el segmento descifrado al buffer general
            decrypted_data += segment_data

        # Decodificar el resultado completo
        if decrypted_data:
            try:
                decoded_string = decrypted_data.decode('utf-8')
                if debug == 1:
                    print(f"Resultado decodificado: {decoded_string}")
                return decoded_string
            except Exception as e:
                if debug == 1:
                    print(f"Error al decodificar")
                return None
        else:
            return None


    def save(self, data, page,debug=0):
        """
        Guarda datos en la EEPROM en texto plano.
        Si los datos son mayores a 64 bytes, se segmentan y se guardan en páginas consecutivas.
        """
        if isinstance(data, str):  # Si los datos son cadena, conviértela a bytes
                data = bytes(data, 'utf-8')
        
        if debug == 1:
            print(f"Datos a guardar: {data}")
        
        extra_space = 0
        page = page * 64
        self.control.write(page, data)  # Guardar en la EEPROM
        
        if debug == 1:
            print(f"Guardado en página {page} Dato: {data}")
    
    def read(self, page, raw=0, debug=0):
        """
        Lee datos desde la EEPROM.
        """
        page = page * 64
        raw_data=self.control.read(page, 64)
        
        if debug == 1:
            print(f"Datos en crudo: {raw_data}")
        
        # Decodificar el resultado dependiendo del tipo de dato original
        if raw_data:  # Asegúrate de que no esté vacío
            if raw == 1:
                return raw_data
            decoded_string = ''
            temp_data = b''
            for byte in raw_data:
                temp_data += bytes([byte])  # Agregar el byte actual a temp_data
                try:
                    # Intentar decodificar el bloque hasta el momento
                    decoded_string += temp_data.decode('utf-8')
                    temp_data = b''  # Reiniciar el temporal si la decodificación fue exitosa
                except Exception as e:
                    if debug == 1:
                        print(f"read -- temp_data:{temp_data} -- Exception found: {e}")
                    pass

            if debug == 1:
                print(f"Resultado plano: {decoded_string}")

            return decoded_string if decoded_string else None
        else:
            return None