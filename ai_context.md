# Contexto del Proyecto: RECTITRACK

## 1. Propósito del Sistema
RectiTrack es un sistema de software a medida diseñado bajo una arquitectura web para transformar la gestión operativa informal de un taller de rectificación de motores en un entorno digital centralizado[cite: 1]. El objetivo principal es eliminar la pérdida de información y la dependencia de órdenes verbales o cuadernos manuales, garantizando la trazabilidad en tiempo real de cada pieza o motor que ingresa al taller[cite: 1, 2].

## 2. Restricciones de Infraestructura y Despliegue
*   **Entorno:** Servidor VPS ejecutando Docker y Docker Compose.
*   **Restricción de Red:** Disponibilidad de **un único puerto público expuesto (`10213`)** en el host debido a limitaciones de IP estática.
*   **Enrutamiento:** SWAG (Nginx de LinuxServer) actúa como Proxy Inverso seguro en el puerto `10213`. Todas las subrutas de la aplicación web se despachan internamente a través de este puerto mediante directivas de proxy de Nginx de tipo *strip-prefix*.
*   **Componentes Activos en `compose.yaml`:**
    *   `mariadb`: Motor de base de datos relacional (Base de datos física: `rectitrack_db`).
    *   `phpmyadmin`: Administrador gráfico de datos accesible internamente.
    *   `swag`: Capa de seguridad HTTPS y enrutador proxy inverso.
    *   `crud`: Backend de la aplicación desarrollado en Python / Flask.

## 3. Modelo de Datos Relacional (`rectitrack_db`)
El esquema de persistencia física en MariaDB está compuesto por las siguientes entidades críticas conectadas:
*   `Cliente`: Almacena información de contacto y credenciales de usuarios externos[cite: 2, 3].
*   `Motor`: Identificado unívocamente mediante un código QR (`codigo_qr`) generado al ingresar la pieza al taller[cite: 2, 3].
*   `OrdenTrabajo`: Controla las fechas de ingreso, montos totales, saldos adeudados y el estado general del motor en el flujo del taller[cite: 2, 3].
*   `Pago_Orden`: Registra anticipos y pagos parciales financieros asociados a una orden[cite: 2, 3].
*   `Area`: Divisiones físicas del taller de mecanizado (`Cilindros`, `Cigüeñal`, `Bujes`, `Plano`)[cite: 1].
*   `Operario`: Personal técnico encargado de ejecutar las tareas de rectificación[cite: 1, 2, 3].
*   `Tarea`: Registro cronológico e inmutable de las operaciones técnicas asignadas por el gerente, que incluye campos específicos para observaciones y mediciones de mecanizado[cite: 1, 2, 3].

## 4. Roles y Casos de Uso del Sistema
El sistema segmenta estrictamente el acceso y las interfaces en función de tres roles de usuario diferenciados[cite: 1, 2]:

### A. Rol Gerente (Foco de Implementación Actual)
*   **CU1 / RF03:** Monitorear la transición y el estado de avance de los motores por el taller para identificar cuellos de botella[cite: 2, 3].
*   **CU2 / RF05:** Asignar formalmente nuevas tareas técnicas a operarios y áreas específicas, destruyendo la dependencia de órdenes verbales[cite: 2, 3].
*   **CU3 / RF01:** Registrar el ingreso físico de motores y generar su correspondiente identificador QR único[cite: 2, 3].
*   **CU5 / RF07:** Supervisar el tablero financiero de cobros, anticipos, saldos pendientes y control de la morosidad[cite: 1, 2, 3].

### B. Rol Operario (Personal Técnico)
*   **CU8 / RF10:** Visualizar la lista de tareas asignadas pendientes y activas ordenadas por prioridad desde dispositivos móviles[cite: 1, 2, 3].
*   **CU9 / RF08:** Escanear códigos QR físicos fijados en las piezas para acceder inmediatamente a las especificaciones técnicas[cite: 1, 2, 3].
*   **CU12 / RF09 / RF11:** Registrar avances técnicos, cargar mediciones precisas del mecanizado y pausar flujos operativos ante la falta de repuestos, emitiendo alertas automáticas al gerente[cite: 1, 2, 3].

### C. Rol Cliente (Usuario de Consulta Externa)
*   **CU13 / CU14 / RF12:** Consultar el porcentaje de avance general de su motor y la fecha estimada de entrega ingresando su identificador sin requerir asistencia telefónica del personal[cite: 1, 2, 3].
*   **CU15 / CU16 / RF13 / RF15:** Visualizar estados de cuenta corporativos y saldos adeudados con opción de pago virtual integrado[cite: 2, 3].

## 5. Estado Actual del Desarrollo
*   **Backend (`crud.py`):** Configurado con Flask y `flask_mysqldb`. Actualmente cuenta con un bypass de login automático para forzar la sesión en rol `gerente` con el fin de agilizar las pruebas y optimización visual.
*   **Rutas del Servidor Flask en Producción:**
    *   `/panel-gerente`: Renderiza el panel principal de opciones del administrador.
    *   `/panel-gerente/asignar`: Procesa la lógica DML de inserción de nuevas tareas técnicas en la base de datos y recupera listas relacionales de áreas, operarios y motores.
    *   `/panel-gerente/stock`: Muestra el estado crítico de insumos e inventario del taller[cite: 3].
    *   `/panel-gerente/pagos`: Calcula de manera dinámica los adelantos y saldos deudores cruzando datos de las tablas `OrdenTrabajo`, `Motor` y `Cliente`.
    *   `/panel-gerente/progreso`: Genera las barras de progreso del taller computando el estado del flujo de mecanizado.
*   **Plantillas Activas (`templates/`):** Estructura adaptada al diseño corporativo de Figma con hojas de estilo responsive basadas en Bootstrap. Archivos: `layout.html`, `panel_gerente.html`, `asignar_tareas.html`, `gestionar_stock.html`, `gestionar_pagos.html` y `progreso_motores.html`.

## 6. Instrucciones para el Agente de IA
1.  **Preservación de Estructuras:** Al modificar el código en `crud.py`, bajo ningún concepto elimines la lógica de conexión a las tablas relacionales existentes en `rectitrack_db` ni las funciones del decorador de sesión del Gerente.
2.  **Fidelidad de Diseño:** Cualquier cambio en los componentes visuales de la carpeta `templates/` debe respetar estrictamente la paleta de colores de RectiTrack (`#0b2545` para azul principal, botones en naranja `#f3722c`) e interfaces limpias adaptadas a entornos móviles y de taller mecánico[cite: 3].
3.  **Aislamiento de Puertos:** No intentes mapear puertos adicionales expuestos al VPS de forma directa. Todo tráfico HTTP/HTTPS entrante debe ser canalizado exclusivamente a través del puerto configurado en SWAG (`10213`) mapeando subrutas de Nginx.