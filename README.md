# Open Secure Lock

### Descripción
Este proyecto presenta un **sistema de acceso inteligente** diseñado para mejorar la seguridad en unidades habitacionales y edificios departamentales. El prototipo combina tecnologías modernas, como **NFC**, **contraseñas numéricas**, y **detección de intrusiones**, para ofrecer una solución accesible, eficiente y confiable para proteger hogares frente a posibles robos o accesos no autorizados.

### Características Principales
- **Doble Autenticación:** Combinación de tarjetas NFC y contraseñas numéricas para maximizar la seguridad.
- **Detección de Intrusión:** Sensores infrarrojos y de presión que alertan sobre accesos no autorizados.
- **Notificaciones en Tiempo Real:** Alertas enviadas vía WhatsApp a usuarios y administradores en caso de intentos de acceso no autorizados.
- **Respaldo Energético:** Sistema alimentado por baterías recargables y puerto de carga externa para asegurar el funcionamiento incluso en cortes de energía.
- **Plataforma Web:** Gestión de usuarios y visualización de bitácoras de accesos mediante una interfaz web intuitiva.
- **Diseño Modular:** Facilita la instalación y el mantenimiento del sistema.

### Instalación
1. **Requisitos de Hardware:**
   - Microcontrolador Raspberry Pi Pico W.
   - Módulo NFC MFRC-522.
   - Pantalla LCD1602 I2C.
   - Sensores infrarrojos y de presión.
   - Otros componentes listados en la sección Inventario de Activos.

2. **Requisitos de Software:**
   - **Thonny IDE:** Para cargar y depurar el código en MicroPython.
   - **CallMeBot API:** Para enviar notificaciones vía WhatsApp.

3. **Pasos para Configurar el Prototipo:**
   - [ ] Instalar y configurar los módulos de hardware según el Diagrama de Conexión.
   - [ ] Cargar el firmware en el microcontrolador utilizando el entorno de desarrollo.
   - [ ] Configurar las credenciales de usuario y administrador en la plataforma web.
   - [ ] Realizar pruebas iniciales para verificar el funcionamiento de los módulos.

### Cómo Funciona
1. **Acceso Seguro:**
   - El usuario escanea su tarjeta NFC y proporciona su contraseña numérica en el teclado.
   - Si la autenticación es exitosa, se desbloquea la cerradura electrónica.
2. **Alerta por Intrusión:**
   - Sensores detectan movimientos sospechosos o aperturas no autorizadas de la puerta.
   - Se envía una notificación a través de WhatsApp al usuario y administrador.
3. **Monitoreo y Gestión:**
   - La plataforma web permite realizar altas, bajas y cambios de usuarios, además de consultar bitácoras.

### Diseño de la Base de Datos

El sistema utiliza una base de datos estructurada que permite gestionar eficientemente la información de usuarios, accesos y registros de actividad. A continuación, se presenta el diseño de la base de datos:

#### Descripción
- **Usuarios:** Almacena información básica de los usuarios, como ID, nombre, tarjeta NFC asociada y contraseña encriptada.
- **Registros de Acceso:** Lleva un historial de accesos exitosos y fallidos, incluyendo la fecha y hora del intento.
- **Administradores:** Contiene las credenciales y permisos del administrador del sistema.
- **Configuraciones:** Guarda datos del sistema.

#### Diagrama de la Base de Datos
![Diagrama de Base de Datos](DiseñoBDEEPROM.png)

### Uso Futuro
El prototipo se puede expandir con:
- Integración de asistentes virtuales como Alexa o Google Assistant.
- Uso de teléfonos móviles con NFC como llaves de acceso.
- Adición de cámaras de vigilancia conectadas al sistema.

### Créditos
Desarrollado por:
- **Erik Alcántara Covarrubias** (ealcantarac1700@alumno.ipn.mx)
- **Benjamín Ortiz Rangel** (bortizr1600@alumno.ipn.mx)
- **Ana Paola Santos Mendoza** (asantosm1700@alumno.ipn.mx)

---

¡Contribuciones y retroalimentación son bienvenidas!
