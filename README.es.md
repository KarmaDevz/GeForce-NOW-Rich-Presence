<div align="center">
  <img src="assets/asset1.jpg" alt="Banner de Presencia Enriquecida de GeForce NOW" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
  <br/>
  <h1>🎮 Presencia Enriquecida de GeForce NOW para Discord</h1>
  <p>
    <strong>Muestra el juego real que estás jugando en GeForce NOW — automáticamente en Windows y Linux.</strong>
  </p>
  
  [🇺🇸 English](./README.md) • [🇪🇸 Español](./README.es.md) • [🇹🇷 Türkçe](./README.tr.md)
  
  <br/>
  <br/>

  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/github/v/release/Enderjua/GeForce-NOW-Rich-Presence?style=for-the-badge&color=00C853&logo=github&label=%C3%9Altima%20Versi%C3%B3n" alt="Última Versión"/>
  </a>
  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases">
    <img src="https://img.shields.io/github/downloads/Enderjua/GeForce-NOW-Rich-Presence/total?style=for-the-badge&color=2962FF&logo=github&label=Descargas" alt="Descargas Totales"/>
  </a>
  
</div>

---

## 🕹️ ¿Qué es esto?

**Presencia Enriquecida de GeForce NOW para Discord** te permite mostrar el **juego real que estás jugando en GeForce NOW** directamente en tu perfil de Discord. ¡Se acabaron los estados genéricos de "Jugando a GeForce NOW"!

Esta es una versión moderna y mejorada (**fork**) que introduce compatibilidad completa multi-OS, soporte nativo de detección en Linux, integración con sesiones de Steam, personalización de detalles y herramientas útiles para recompensas de Discord. 🎮💚

---

## ✨ Características y Grandes Mejoras

* 🐧 **Soporte completo para Linux (Wayland y X11)** `[¡Nuevo / Agregado!]`
  * Integración nativa con sistemas Linux. Utiliza la API de scripts de KDE KWin / DBus en Wayland, y realiza una caída automática a `xdotool` en entornos X11 clásicos. Sin necesidad de Wine ni capas pesadas de compatibilidad.
* 🌐 **Integración en tiempo real con Steam (Scraping)** `[¡Nuevo!]`
  * Obtiene tu estado de Steam directamente usando las cookies locales del navegador (Edge/Chrome completamente automatizado, o manual). Permite mostrar estados de sesión enriquecidos (*"En juego: Dota 2"*, salas activas) en tiempo real.
* 🎁 **Modo Quest de Discord (Multi-Presencia)** `[¡Nuevo!]`
  * ¡Desbloquea las recompensas de Discord fácilmente! Simula de forma limpia múltiples instancias de juegos en segundo plano (límite de 15 minutos por juego) mediante subprocesos temporales aislados.
* ✏️ **Campos de presencia personalizables** `[¡Nuevo!]`
  * Edita manualmente los detalles (Línea 1), estado (Línea 2) y tamaño del grupo directamente desde el menú de la bandeja del sistema.
* 🎨 **Interfaz Oscura Premium (Gaming)** `[¡Nuevo!]`
  * Nuevo tema visual oscuro y moderno en todos los diálogos y ventanas Qt5 interactivos de la aplicación.
* ⚡ **Actualizador automático de WebDriver (Windows)**
  * Verificación y descarga inteligente del Edge WebDriver para la extracción de cookies.
* ✅ **Plug & Play**: Funciona de forma automática y al instante tras iniciarse.

---

## 📥 Instalación y Configuración

### 🪟 Windows

1. Descarga el instalador ejecutable `.exe` desde nuestras [Últimas Versiones](https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest).
2. Ejecuta el archivo de instalación y completa los pasos del asistente.
3. Abre la aplicación. Permanecerá activa y minimizada en tu bandeja del sistema (esquina inferior derecha).
4. ¡Inicia cualquier juego en GeForce NOW y observa cómo se actualiza tu perfil al instante!

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, etc.)

Dado que GFN se ejecuta en Linux a través de navegadores web o wrappers de Electron, puedes lanzar la aplicación directamente desde el código fuente:

1. **Clona el repositorio:**
   ```bash
   git clone https://github.com/Enderjua/GeForce-NOW-Rich-Presence.git
   cd GeForce-NOW-Rich-Presence
   ```
2. **Crea y activa un entorno virtual de Python:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Instala las dependencias requeridas:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Nota: Asegúrate de tener instalado `xdotool` si utilizas un gestor de ventanas clásico bajo X11).*
4. **Ejecuta la aplicación:**
   ```bash
   PYTHONPATH=. python3 src/GeForceNOWRichPresence.py
   ```
   *(Para sesiones bajo Wayland nativo, el sistema se acoplará directamente a las APIs del gestor KWin).*

---

## ⚙️ Menú de la Bandeja de Sistema

Haz clic derecho sobre el icono en la bandeja del sistema para configurar las opciones activas:

| Comando | Descripción |
| :--- | :--- |
| 🎮 **Forzar Juego...** | Sobrescribe la detección automática para mostrar el juego que elijas. |
| 🎁 **Modo Quest de Discord** | Lanza ejecuciones simuladas para completar misiones y recompensas. |
| ✅ **Obtener Cookie de Steam** | Extrae tu sesión activa del navegador para obtener detalles de Steam. |
| 👥 **Establecer tamaño máximo...**| Configura los límites de grupo de tu presencia actual. |
| 🚀 **Abrir GeForce NOW** | Abre rápidamente la aplicación oficial de NVIDIA. |
| 📊 **Sincronizar base de datos** | Descarga y actualiza la caché de aplicaciones detectables de Discord. |
| 📝 **Abrir Logs** | Muestra el archivo de registro de depuración en segundo plano. |
| ❌ **Salir** | Cierra la aplicación por completo. |

---

## 🧠 Funcionamiento Interno

El programa actúa como un servicio local en segundo plano:
1. **Rastrea** las ventanas activas (usando llamadas nativas del sistema, DBus/KWin en Wayland o Win32 APIs en Windows).
2. **Limpia** el título para extraer únicamente el nombre puro del juego.
3. **Consulta** los metadatos o busca el identificador coincidente en el catálogo oficial de Discord.
4. **Lanza** un proceso simulado mínimo aislado en un directorio temporal para registrar la presencia directa dentro de tu cliente de Discord Desktop.

---

## 🧩 Preguntas Frecuentes (FAQ)

**P: ¿Es necesario tener instalado Python o dependencias en Windows?**  
R: ¡No! El paquete para Windows incluye todo lo necesario en un único archivo ejecutable listo para usar.

**P: ¿Es seguro utilizar este programa?**  
R: Completamente. Se ejecuta a nivel local, no solicita contraseñas ni credenciales y funciona de manera transparente junto a tu cliente oficial de juego.

---

## 💬 Autores, Soporte y Contacto

Este proyecto es el resultado del trabajo y colaboración de:

* 🧑‍💻 **KarmaDevz** - Creador original y desarrollador principal del núcleo y empaquetado para Windows.
  * [Perfil de GitHub](https://github.com/KarmaDevz) • [Soporte por PayPal](https://paypal.me/KarmaDevz)
* 🛠️ **Enderjua** - Mantenedor del fork, integración nativa con Linux, desarrollo del Modo Quest y mejoras en las funcionalidades.
  * **GitHub Fork:** [Enderjua/GeForce-NOW-Rich-Presence](https://github.com/Enderjua/GeForce-NOW-Rich-Presence)
  * **Servidor de Discord:** [Únete a nuestro Servidor de Soporte](https://discord.gg/A9ESFRTzqR)
  * **Correo Electrónico:** enderjua@gmail.com
  * **Instagram:** [@marijuabakunin](https://instagram.com/marijuabakunin)

---

<div align="center">
  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/badge/Descargar%20Ahora%20➡️-1B5E20?style=for-the-badge&logo=nvidia&logoColor=white" alt="Descargar ahora"/>
  </a>
</div>
