# 📖 Guía Detallada e Instrucciones de Uso

Bienvenido a la guía completa de **GeForce NOW Rich Presence**. En este documento encontrarás explicaciones paso a paso sobre cómo aprovechar todas las funciones de la aplicación, así como la configuración detallada de la cookie de Steam para enriquecer tu presencia en Discord.

---

## 📑 Tabla de Contenidos
1. [Primeros Pasos y Funcionamiento General](#-primeros-pasos-y-funcionamiento-general)
2. [🔑 Configuración de la Cookie de Steam](#-configuración-de-la-cookie-de-steam)
   - [¿Por qué se necesita la cookie?](#por-qué-se-necesita-la-cookie)
   - [¿Por qué se realiza de forma manual?](#por-qué-se-realiza-de-forma-manual)
   - [Paso a paso: Cómo obtener `steamLoginSecure`](#paso-a-paso-cómo-obtener-steamloginsecure)
     - [En Microsoft Edge / Google Chrome / Brave / Opera](#en-microsoft-edge--google-chrome--brave--opera)
     - [En Mozilla Firefox](#en-mozilla-firefox)
   - [Cómo ingresar la cookie en la aplicación](#cómo-ingresar-la-cookie-en-la-aplicación)
3. [🎯 Modo Misiones (Discord Quests)](#-modo-misiones-discord-quests)
4. [🎮 Forzar Juego Manualmente](#-forzar-juego-manualmente)
5. [🛠️ Diagnóstico y Preguntas Frecuentes](#-diagnóstico-y-preguntas-frecuentes)

---

## 🚀 Primeros Pasos y Funcionamiento General

La aplicación se ejecuta discretamente en la **bandeja del sistema (system tray)**, junto al reloj de Windows:

1. **Detección Automática**: Al iniciar cualquier juego en la aplicación oficial de GeForce NOW, el programa detecta la ventana activa y actualiza automáticamente tu estado en Discord con el título oficial, arte gráfico y tiempo de partida.
2. **Sincronización en la Nube**: La base de datos de juegos compatibles se actualiza dinámicamente desde el menú contextual (*Sincronizar Juegos*).

---

## 🔑 Configuración de la Cookie de Steam

### ¿Por qué se necesita la cookie?
La cookie **`steamLoginSecure`** permite que la aplicación consulte de forma segura a los endpoints comunitarios de Steam para enriquecer tu presencia en Discord con:
- Información de salas y lobbies multijugador en tiempo real.
- Conteo de jugadores y estado dentro del servidor de la partida.
- Detalles extendidos y estado de sesión de los juegos que estés jugando en GeForce NOW.

> [!NOTE]
> La cookie de Steam es **opcional**. Si decides no configurarla, la detección de juegos en GeForce NOW y la presencia básica en Discord seguirán funcionando con normalidad.

---

### ¿Por qué se realiza de forma manual?
Los navegadores modernos basados en Chromium (como Microsoft Edge y Google Chrome a partir de sus versiones 127+) incorporan una protección de seguridad llamada **App-Bound Encryption (`v20`)**. Esta característica cifra las cookies vinculándolas exclusivamente al ejecutable oficial del navegador, bloqueando cualquier intento de extracción externa automatizada por software de terceros.

Por ello, la vía más segura, confiable y rápida es copiar el valor de la cookie directamente desde las Herramientas de Desarrollador de tu navegador.

---

### Paso a paso: Cómo obtener `steamLoginSecure`

#### En Microsoft Edge / Google Chrome / Brave / Opera

1. Abre tu navegador web y entra a [https://steamcommunity.com](https://steamcommunity.com).
2. Inicia sesión con tu cuenta de Steam si aún no lo has hecho.
3. Presiona la tecla <kbd>F12</kbd> (o haz clic derecho en cualquier parte de la página y selecciona **Inspeccionar**).
4. En el panel de herramientas que se abrirá:
   - Ve a la pestaña superior **Aplicación** (en inglés, *Application*).  
     *(Si no la ves, haz clic en el ícono `>>` para ver las pestañas ocultas)*.
   - En el menú lateral izquierdo, despliega la sección **Almacenamiento** $\rightarrow$ **Cookies**.
   - Haz clic sobre `https://steamcommunity.com`.
5. En la lista de cookies de la derecha:
   - Localiza la fila con el nombre **`steamLoginSecure`**.
   - Haz doble clic sobre su valor en la columna **Valor de la cookie** (Cookie Value) y cópialo (<kbd>Ctrl</kbd> + <kbd>C</kbd>).

```
Ejemplo de formato:
76561198xxxxxxxx%7C%7CeyAidG9rZW4iOiAi...
```

---

#### En Mozilla Firefox

1. Entra a [https://steamcommunity.com](https://steamcommunity.com) con tu sesión iniciada.
2. Presiona <kbd>F12</kbd> para abrir las Herramientas de Desarrollador.
3. Ve a la pestaña **Almacenamiento** (*Storage*).
4. En el menú lateral izquierdo, despliega **Cookies** y selecciona `https://steamcommunity.com`.
5. Busca la cookie llamada **`steamLoginSecure`** y copia su valor.

---

### Cómo ingresar la cookie en la aplicación

Dispones de dos métodos sencillos para configurarla:

#### Método 1: Desde la Bandeja del Sistema (Recomendado)
1. Haz clic derecho en el icono de **GeForce NOW Presence** junto al reloj de Windows.
2. Selecciona la opción **🔑 Configurar cookie de Steam**.
3. Pega el valor de la cookie copiada en el cuadro de texto y haz clic en **Aceptar**.
4. La aplicación validará inmediatamente la cookie con los servidores de Steam y te mostrará una notificación confirmando que ha sido guardada.

#### Método 2: Mediante el archivo `.env`
1. Abre el archivo [`.env`](file:///.env) ubicado en la carpeta raíz del programa con cualquier editor de texto (Bloc de notas, VS Code, etc.).
2. Ubica la línea:
   ```env
   STEAM_COOKIE=''
   ```
3. Pega tu valor entre las comillas simples:
   ```env
   STEAM_COOKIE='76561198xxxxxxxx%7C%7CeyAidG9rZW4iOiAi...'
   ```
4. Guarda el archivo. El programa la cargará automáticamente.

---

## 🎯 Modo Misiones (Discord Quests)

El **Modo Misiones** permite simular la ejecución de juegos específicos requeridos por las misiones promocionales de Discord:

- Puedes buscar y seleccionar el juego objetivo en el catálogo de misiones de la aplicación.
- Cada instancia simulada se mantendrá en ejecución durante **16 minutos y 30 segundos** (tiempo suficiente para cumplir con los requisitos habituales de 15 minutos en Discord).
- Al finalizar el temporizador, el proceso simulado se cerrará automáticamente de forma limpia.

---

## 🎮 Forzar Juego Manualmente

Si juegas a un título que acaba de añadirse a GeForce NOW y aún no está registrado en la base de datos de detección automática:
1. Haz clic derecho en el icono de la bandeja del sistema.
2. Selecciona **🎮 Forzar Juego...**.
3. Escribe o selecciona el nombre del juego que deseas que aparezca en tu perfil de Discord.
4. Para volver al modo normal, selecciona la opción para restaurar la detección automática.

---

## 🛠️ Diagnóstico y Preguntas Frecuentes

- **Discord no muestra el estado de actividad**: Asegúrate de tener Discord abierto y con la opción *"Mostrar la actividad actual como un mensaje de estado"* activada en la sección **Ajustes de usuario** $\rightarrow$ **Privacidad de la actividad** de Discord.
- **¿Qué pasa si mi cookie expira?**: Las cookies de sesión de Steam suelen durar varias semanas o meses. Si cierras sesión manualmente en Steam desde tu navegador, la cookie caducará. Si esto sucede, simplemente repite el proceso de copia y vuelve a pegarla en la aplicación.
- **Ver registros del sistema**: Puedes revisar el visor de registros en tiempo real haciendo clic derecho en el icono de la bandeja $\rightarrow$ **Herramientas de diagnóstico** $\rightarrow$ **Ver Registros**.
- **En macOS aparecen múltiples avisos de seguridad / componentes bloqueados (Gatekeeper)**:
  Al descargar la aplicación en macOS desde GitHub, el sistema operativo le asigna un atributo de cuarentena (`com.apple.quarantine`) a cada archivo y librería interna de Python. Para desbloquear todos los componentes de una sola vez sin tener que aceptar popups individuales:
  1. Abre la **Terminal** en tu Mac.
  2. Escribe `xattr -cr ` (dejando un espacio al final).
  3. Arrastra y suelta la carpeta descomprimida `GeForceNOWRichPresence` dentro de la ventana de la Terminal (la ruta se completará automáticamente).
  4. Presiona <kbd>Enter</kbd>.
  5. *(Opcional)* Asegúrate de otorgar permisos de ejecución: `chmod +x /ruta/a/GeForceNOWRichPresence/GeForceNOWRichPresence`.
  6. Ejecuta el programa con normalidad.

