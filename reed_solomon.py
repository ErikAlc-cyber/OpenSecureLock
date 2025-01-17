import random

class ReedSolomonSimple:
    def __init__(self):
        pass

    @staticmethod
    def calculate_parity(data):
        """
        Genera una paridad XOR para cada byte en los datos, proporcionando corrección por posición.
        """
        parity = []
        for byte in data:
            parity.append(byte ^ 0xFF)  # Operación XOR con 0xFF para generar paridad específica
        return parity

    @staticmethod
    def encode(data):
        """
        Codifica los datos originales añadiendo paridad.
        `data`: El mensaje original como string.
        """
        if isinstance(data, bytes):
        # Si data ya es bytes, no necesitas codificarlo.
            data = list(data)
        else:
        # Si data es string, conviértelo a bytes y luego a lista.
            data = list(data.encode('utf-8'))

        # Generamos paridad y anexamos a los datos
        parity = ReedSolomonSimple.calculate_parity(data)
        encoded_data = data + parity
        return encoded_data

    @staticmethod
    def detect_and_correct_errors(encoded_data):
        """
        Detecta y corrige un error simple en los datos codificados.
        `encoded_data`: Lista de bytes de datos codificados con paridad añadida.
        """
        length = len(encoded_data) // 2
        data, parity = encoded_data[:length], encoded_data[length:]

        # Detectamos y corregimos errores
        error_index = -1
        for i in range(length):
            calculated_parity = data[i] ^ 0xFF
            if calculated_parity != parity[i]:
                error_index = i
                break  # Salimos si detectamos un único error

        if error_index != -1:
            # Intentamos corregir el byte en la posición con el error
            correct_value = parity[error_index] ^ 0xFF
            data[error_index] = correct_value

        # Convertimos de vuelta a string los datos corregidos
        decoded_data = bytes(data).decode('utf-8')
        return decoded_data
    
    def pseudo_encrypt(mensaje):
        mensaje_con_error = ReedSolomonSimple.encode(mensaje)
        len_mesj = len(mensaje)
        # Introducimos varios errores en posiciones aleatorias dentro de los datos (no en la paridad)
        for pos in range(len_mesj):
            # Aseguramos que el error mantenga el byte dentro de un rango visible ASCII (32-126)
            original_byte = mensaje_con_error[pos]
            new_byte = original_byte
            while new_byte == original_byte or not (32 <= new_byte <= 126):
                new_byte = original_byte ^ random.randint(1, 95)  # Genera bytes dentro del rango ASCII visible
            mensaje_con_error[pos] = new_byte  # Asigna el nuevo byte
        return mensaje_con_error

    def pseudo_decrypt(mensaje_con_error):
        len_mesj = int(len(mensaje_con_error) / 2)
        for j in range(len_mesj):  # Realizamos varias pasadas, una por cada error
            mensaje_decodificado = ReedSolomonSimple.detect_and_correct_errors(mensaje_con_error)
            mensaje_con_error = list(mensaje_decodificado.encode('utf-8')) + mensaje_con_error[len_mesj:]
        mensaje_final = ''.join(chr(b) for b in mensaje_con_error[:len_mesj])
        return mensaje_final

