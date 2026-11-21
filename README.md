# 📻 RPi Internet Radio & Weather Station

Reproductor autónomo de radio por internet construido sobre **Raspberry Pi 3 Model B** con pantalla **LCD 3.5" (480x320)** en modo kiosco y control remoto desde cualquier navegador en la red local.

> **Nota de Hardware:** La controladora táctil (`XPT2046`) de la pantalla LCD que tengo se encuentra dañada/inoperativa, por lo que la LCD actúa exclusivamente como visor de estado, reloj y clima, mientras que el control de emisoras y reproducción se realiza desde un teléfono celular o PC conectado a la red local (`http://<IP-RASPBERRY>:8080`), los cambios desde el celular se reflejan de inmediato en la raspberry.

---

## ✨ Características Principales

* **Reproducción Autónoma al Encender:** Inicia automáticamente la emisora principal (`El Conquistador`) al arrancar el sistema mediante **MPD (Music Player Daemon)** sin requerir interacción física.
* **Control Remoto vía Web Local:** Interfaz web responsiva accesible desde el navegador del celular en `http://<IP-RASPBERRY>:8080` para cambiar de emisora o pausar/reanudar, reflejando los cambios en la LCD en tiempo real (sincronización cada 2 segundos).
* **Reloj Digital Local:** Sincronizado con zona horaria `America/Santiago`.
* **Pronóstico del Clima en Vivo:** Tarjetas laterales para **Hoy** (temperatura actual, estado y mínima/máxima) y **Mañana** (estado y mínima/máxima) mediante la API pública de **Open-Meteo** (sin necesidad de API Key) con caché local de 30 minutos.
* **Modo Nocturno Automático:** Atenuación de brillo por software (`brightness: 0.25`) activa automáticamente entre las **23:00 y las 07:30**.
* **Modo Kiosco Limpio:** Bloqueo de suspensión de pantalla (`DPMS`), ocultamiento del puntero (`unclutter`) y supresión de burbujas de traducción mediante políticas administradas de Chromium.

---

## 🛠️ Hardware Utilizado

* **Placa:** Raspberry Pi 3 Model B (v1.2).
* **Pantalla:** LCD TFT 3.5" SPI (`480x320`), controlador de video **ILI9486** *(panel táctil XPT2046 averiado, usada en modo solo visualización)*.
* **Salida de Audio:** Jack analógico integrado de 3.5 mm (`ALSA` / `Headphones`).
* **Almacenamiento y Energía:** MicroSD (Raspberry Pi OS Lite Trixie) + fuente 5V 2.5A.

---

## 🏗️ Arquitectura y Stack de Software

```text
+-------------------------------------------------------------------+
|                        Raspberry Pi 3B                            |
|                                                                   |
|  +------------------+      HTTP / JSON       +-----------------+  |
|  |  Chromium Kiosk  | <--------------------- |   Flask Server  |  |
|  | (LCD Solo Visor) |                        |  (Puerto 8080)  |  |
|  +------------------+                        +--------+--------+  |
|                                                       ^           |
|  +------------------+      HTTP / JSON (Control)      |           |
|  |  Celular / PC    | <-------------------------------+           |
|  |   (Red Local)    |                                             |
|  +------------------+                     +-----------+--------+  |
|                                           |                    |  |
|                                           v                    v  |
|                                  +----------------+   +--------+  |
|                                  |  MPD + mpc     |   | Open-  |  |
|                                  | (Audio Stream) |   | Meteo  |  |
|                                  +-------+--------+   +--------+  |
|                                          |                        |
|                                          v                        |
|                                  +----------------+               |
|                                  | ALSA Jack 3.5  |               |
|                                  |  (plughw:1,0)  |               |
|                                  +----------------+               |
+-------------------------------------------------------------------+
