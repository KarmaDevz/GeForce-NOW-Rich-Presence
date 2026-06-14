<div align="center">
  <img src="assets/asset1.jpg" alt="Banner de Presencia Enriquecida de GeForce NOW" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
  <br/>
  <h1>🎮 Presencia Enriquecida de GeForce NOW para Discord</h1>
  <p>
    <strong>Muestra el juego que realmente estás jugando en Discord mientras usas GeForce NOW — automáticamente y con estilo.</strong>
  </p>
  
  [🇺🇸 Read in English](./README.md) • [🇷🇺 На русском](./README.ru.md) • [📥 Descargar Última Versión](#-instalación) • [💬 Soporte](#-acerca-de-y-soporte)
  
  <br/>

  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/github/v/release/KarmaDevz/GeForce-NOW-Rich-Presence?style=for-the-badge&color=00C853&logo=github&label=%C3%9Altima%20Versi%C3%B3n" alt="Última Versión"/>
  </a>
  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases">
    <img src="https://img.shields.io/github/downloads/KarmaDevz/GeForce-NOW-Rich-Presence/total?style=for-the-badge&color=2962FF&logo=github&label=Descargas%20Totales" alt="Descargas Totales" />
  </a>
  <img src="https://img.shields.io/badge/Plataformas-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen?style=for-the-badge" alt="Plataformas Soportadas"/>
  
</div>

---

## 🕹️ ¿Qué es esto?

Por defecto, Discord solo muestra un estado genérico de **"Jugando a NVIDIA GeForce NOW"** cuando transmites tus juegos. Esta aplicación se ejecuta silenciosamente en la bandeja del sistema, escanea tu transmisión activa de GeForce NOW, la compara con una base de datos local y la reemplaza en tiempo real por el **nombre real del juego, descripción, tamaño del grupo activo y el arte gráfico correspondiente** en tu perfil de Discord.

---

## ✨ Características

- 🔍 **Detección Dinámica de Juegos**: Monitorea de forma automática el juego activo en GeForce NOW mediante el análisis de ventanas en ejecución.
- 🎯 **Modo Misiones (Discord Quests)**: Agrega y simula múltiples instancias de juegos simultáneamente para completar misiones de Discord (cada simulación corre durante 16 minutos y 30 segundos antes de cerrarse de forma automática).
- 🔑 **Gestor de Cookies de Steam**: Extrae de manera segura tu sesión de Steam local a través de Selenium y `browser-cookie3` para mostrar información enriquecida (salas de juego, número de jugadores y estados detallados).
- 🛠️ **Centro de Diagnóstico**: Visor de registros (logs) integrado con resaltado de sintaxis y cuadro de diálogo con reportador de fallos automático para copiar detalles del error al portapapeles al instante.
- 🔄 **Actualizaciones Silenciosas Multiplataforma**: Actualizador en segundo plano integrado que detecta, descarga y extrae dinámicamente las actualizaciones para Windows, macOS y Linux sin bucles infinitos.
- 🚀 **Inicio Automático**: Configura fácilmente el arranque con el sistema operativo directamente desde el menú de la bandeja.
- 💻 **100% Multiplataforma**: Soporte y compilaciones nativas para Windows, macOS y Linux.

---

## 📸 En Acción

<div align="center">
  <img src="assets/instrucciones.png" width="95%" alt="Discord Rich Presence Instrucciones" style="border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);"/>
</div>

---

## ⚙️ Opciones del Icono en la Bandeja

Accede a la configuración y características directamente desde el menú de la bandeja del sistema:

| Categoría | Opción | Descripción |
| :--- | :--- | :--- |
| **Acciones** | 🎮 **Forzar Juego...** | Sobrescribe manualmente la detección automática y elige qué juego mostrar. |
| | 📊 **Sincronizar Juegos** | Descarga la base de datos más reciente de equivalencia de juegos desde la nube. |
| | 👥 **Modo Misiones...** | Abre el panel de misiones para añadir, monitorear y cerrar simulaciones de misiones. |
| **Credenciales**| 🔑 **Obtener Cookie de Steam** | Autentica y obtiene cookies locales para una integración más profunda con Steam. |
| **Preferencias**| ⚙️ **Preferencias de Inicio** | Activa/Desactiva el inicio automático con el sistema operativo. |
| | 📥 **Instalar Actualización** | Se muestra únicamente cuando hay una versión más reciente lista para descargar. |
| **Sistema** | 📝 **Herramientas de diagnóstico** | Abre el visor de registros (logs) del programa. |
| | ℹ️ **Acerca de** | Muestra la información de la aplicación y la versión que está corriendo actualmente. |
| | ❌ **Salir** | Cierra la aplicación por completo y detiene todos los procesos en segundo plano. |

---

## 🛠️ Arquitectura y Tecnologías Utilizadas

Esta aplicación está construida con librerías modernas y eficientes de Python:
* **Entorno de Interfaz**: `PyQt5` para una interfaz de usuario oscura y moderna que encaja con la estética gamer.
* **Integración con Discord**: `pypresence` para comunicación RPC de Discord de baja latencia.
* **Monitoreo de Procesos**: `psutil` para vigilar GeForce NOW y cerrar procesos simulados residuales.
* **Automatización**: `selenium` y `browser-cookie3` para extraer cookies de inicio de sesión de navegadores locales.
* **Empaquetado**: `PyInstaller` para generar ejecutables autónomos ligeros y portables.
* **Integración Continua (CI/CD)**: Compilaciones a través de matrices de `GitHub Actions` en runners de Windows, macOS y Linux.

---

## 📥 Instalación

### Windows
1. Descarga el instalador (`GeForcePresenceSetup.exe`) o el archivo ejecutable portable (`GeForceNOWRichPresence-Windows.zip`) desde la página de [**Última Versión**](https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest).
2. Ejecuta el instalador e inicia el programa. Se ejecutará en la bandeja del sistema.

### macOS
1. Descarga el archivo `GeForceNOWRichPresence-macOS.zip`.
2. Extrae la carpeta y ejecuta el binario.

### Linux
1. Descarga el archivo `GeForceNOWRichPresence-Linux.tar.gz`.
2. Extrae los archivos, marca el binario como ejecutable (`chmod +x GeForceNOWRichPresence`) y ejecútalo.

---

## 💻 Compilación Local y Desarrollo

Si quieres ejecutar el proyecto desde el código fuente o compilarlo en tu máquina:

### 1. Requisitos
* Python 3.12+
* Google Chrome, Microsoft Edge o un navegador compatible (para la obtención de cookies de Steam)

### 2. Configurar Entorno Virtual
```bash
# Clonar el repositorio
git clone https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence.git
cd GeForce-NOW-Rich-Presence

# Crear el entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .\.venv\Scripts\activate

# Instalar requerimientos
pip install -r requirements.txt
pip install pyinstaller
```

### 3. Ejecutar desde el Código Fuente
```bash
python -m src.GeForceNOWRichPresence
```

### 4. Compilar Localmente
Para compilar la aplicación utilizando PyInstaller de forma local:
```bash
pyinstaller --clean --noconfirm GeForceNOWRichPresence.spec
```
Los ejecutables resultantes se guardarán dentro de la carpeta `dist/GeForceNOWRichPresence/`.

---

## 💬 Acerca de y Soporte

Creado por [**KarmaDevz**](https://github.com/KarmaDevz) para unir lo mejor del gaming en la nube y los perfiles de Discord.

⭐️ **¿Te gusta el proyecto?** ¡Consigna una estrella (⭐) al repositorio en GitHub para ayudarnos a crecer!

<div align="center">
  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/badge/Descargar%20Ahora%20➡️-1B5E20?style=for-the-badge&logo=nvidia&logoColor=white" alt="Descargar ahora"/>
  </a>
  <a href="https://paypal.me/KarmaDevz" target="_blank">
    <img src="https://img.shields.io/badge/💖%20Apoyar%20este%20Proyecto-0070ba?style=for-the-badge&logo=paypal&logoColor=white" alt="Donar en PayPal">
  </a>
</div>

<br/>

<div align="center">
  <h3>🆘 ¿Necesitas Soporte?</h3>
  <p>¡Únete al servidor oficial de <strong>GeForce NOW by Digevo</strong> en Discord para charlar y resolver dudas con la comunidad!</p>
  <a href="https://discord.gg/geforce-now-by-digevo-1412524071878525050">
    <img src="https://img.shields.io/badge/Únete%20al%20Servidor%20de%20Discord-2962FF?style=for-the-badge&logo=discord&logoColor=white" alt="GeForce NOW by Digevo"/>
  </a>
</div>
