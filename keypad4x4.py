from machine import Pin
import utime

class Keypad4x4:
    """
    Clase para manejar un teclado matricial 4x4.
    """

    def __init__(self):
        """
        Inicializa los pines para las filas y columnas del teclado.
        """
        self.col_list = [26, 15, 14, 13]  # Pines para las columnas
        self.row_list = [12, 11, 10, 9]   # Pines para las filas

        # Configurar las filas como salidas y establecer el valor inicial a alto
        for i in range(4):
            self.row_list[i] = Pin(self.row_list[i], Pin.OUT)
            self.row_list[i].value(1)

        # Configurar las columnas como entradas con pull-up
        for i in range(4):
            self.col_list[i] = Pin(self.col_list[i], Pin.IN, Pin.PULL_UP)

        # Mapa de teclas
        self.key_map = [
            ["D", "#", "0", "*"],
            ["C", "9", "8", "7"],
            ["B", "6", "5", "4"],
            ["A", "3", "2", "1"]
        ]

    def Keypad4x4Read(self):
        """
        Lee el estado del teclado y devuelve la tecla presionada.
        
        :return: Tecla presionada o None si no hay tecla presionada.
        """
        for r in self.row_list:
            r.value(0)  # Activa la fila actual
            result = [col.value() for col in self.col_list]  # Lee el estado de las columnas
            
            if min(result) == 0:  # Si alguna columna está en estado bajo
                key = self.key_map[self.row_list.index(r)][result.index(0)]  # Obtiene la tecla correspondiente
                r.value(1)  # Vuelve a establecer la fila a alto
                return key
            
            r.value(1)  # Vuelve a establecer la fila a alto después de la lectura

        return None  # Retorna None si no se presiona ninguna tecla

    def ReadString(self):
        """
        Lee una cadena de caracteres del teclado hasta que se presiona '#'.
        
        :return: Cadena de caracteres ingresada.
        """
        string = ""
        while True:
            key = self.Keypad4x4Read()
            if key is not None:
                if key == "#":  # Fin de la entrada
                    return string
                string += key  # Agrega la tecla a la cadena
                utime.sleep(0.3)  # Espera un tiempo para evitar múltiples lecturas
