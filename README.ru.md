<div align="center">
  <img src="assets/asset1.jpg" alt="GeForce NOW Rich Presence Banner" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
  <br/>
  <h1>🎮 GeForce NOW Rich Presence для Discord</h1>
  <p>
    <strong>Продемонстрируйте свою игру в Discord во время игры через GeForce NOW — автоматически и красиво.</strong>
  </p>
  
  [🇺🇸 Read in English](./README.md) • [🇪🇸 Leer en Español](./README.es.md) • [📥 Скачать последнюю версию](#-installation) • [💬 Поддержка](#-about--support)
  
  <br/>

  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/github/v/release/KarmaDevz/GeForce-NOW-Rich-Presence?style=for-the-badge&color=00C853&logo=github&label=Latest%20Release" alt="Latest Release"/>
  </a>
  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases">
    <img src="https://img.shields.io/github/downloads/KarmaDevz/GeForce-NOW-Rich-Presence/total?style=for-the-badge&color=2962FF&logo=github&label=Downloads" alt="Total Downloads"/>
  </a>
  <img src="https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen?style=for-the-badge" alt="Supported Platforms"/>
  
</div>

---

## 🕹️ Что это такое?

По умолчанию Discord отображает только общий статус **"Играет в NVIDIA GeForce NOW"** при трансляции игр. Это приложение незаметно работает в системном трее, сканирует активный поток GeForce NOW, сопоставляет его с локальной базой данных и в режиме реального времени заменяет его на **фактическое название игры, описание, количество активных игроков и соответствующую обложку игры** в вашем профиле Discord.

---

## ✨ Возможности

- 🔍 **Динамическое обнаружение игр**: Автоматически отслеживает запущенные в GeForce NOW игры путем анализа активного окна.
- 🎯 **Режим квестов (Discord Quests)**: Одновременный запуск и симуляция нескольких игровых сессий для выполнения квестов Discord (каждая симуляция длится 16 минут 30 секунд, после чего автоматически закрывается).
- 🔑 **Менеджер файлов cookie Steam**: Безопасно извлекает файлы cookie вашей локальной сессии Steam с помощью Selenium и `browser-cookie3` для получения подробной информации о лобби Steam, количестве игроков и расширенном статусе игры.
- 🛠️ **Центр диагностики**: Встроенное окно просмотра логов с подсветкой синтаксиса и диалог автоматического отчета об ошибках для мгновенного копирования трассировки стека (traceback).
- 🔄 **Кроссплатформенные тихие обновления**: Встроенный инструмент фонового обновления, который динамически обнаруживает, скачивает и распаковывает обновления для Windows, macOS и Linux без бесконечных всплывающих окон.
- 🚀 **Настройки автозапуска**: Легко настраивайте запуск приложения вместе с операционной системой прямо из меню в системном трее.
- 💻 **100% Кроссплатформенность**: Нативные сборки и поддержка Windows, macOS и Linux.

---

## 📸 В действии

<div align="center">
  <img src="assets/instructions.png" width="95%" alt="Discord Rich Presence Instructions" style="border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);"/>
</div>

---

## ⚙️ Функции иконки в трее

Доступ к настройкам и возможностям программы осуществляется напрямую из контекстного меню в системном трее:

| Категория | Опция | Описание |
| :--- | :--- | :--- |
| **Действия** | 🎮 **Принудительный запуск игры...** | Вручную переопределить обнаружение и выбрать конкретную игру для отображения. |
| | 📊 **Синхронизировать игры** | Загрузить актуальную базу данных соответствия игр из облака. |
| | 👥 **Режим квестов...** | Открыть панель списка квестов для добавления, мониторинга и закрытия активных симуляций. |
| **Данные**| 🔑 **Получить cookie-файл Steam** | Выполнить авторизацию и извлечь cookie-файлы для более глубокой интеграции со Steam. |
| **Настройки**| ⚙️ **Параметры автозапуска** | Включить или выключить запуск вместе с ОС (управление ярлыками в папке автозагрузки Windows). |
| | 📥 **Установить обновление** | Отображается только тогда, когда новая версия готова к загрузке. |
| **Система** | 📝 **Средства диагностики** | Открыть встроенное окно просмотра логов приложения в реальном времени. |
| | ℹ️ **О программе** | Просмотреть информацию о приложении и текущую версию. |
| | ❌ **Выход** | Полностью завершить работу приложения и закрыть все фоновые процессы. |

---

## 🛠️ Технологический стек и архитектура

Это приложение создано с использованием современных и эффективных библиотек Python:
* **Интерфейс (UI)**: `PyQt5` для отзывчивого десктопного клиента в темном игровом стиле, соответствующем общей теме.
* **Интеграция с Discord**: `pypresence` для работы с Discord RPC с минимальной задержкой.
* **Отслеживание процессов**: `psutil` для безопасного мониторинга GeForce NOW и удаления оставшихся фейковых/симуляционных исполняемых файлов.
* **Автоматизация браузера**: `selenium` и `browser-cookie3` для безопасного сбора локальных данных браузера.
* **Сборка проекта**: `PyInstaller` для создания портативных, легковесных автономных исполняемых файлов.
* **CI/CD Сборка**: Матричные сборки `GitHub Actions` для компиляции исполняемых файлов непосредственно на виртуальных машинах Windows, macOS и Linux.

---

## 📥 Установка

### Windows
1. Скачайте установщик (`GeForcePresenceSetup.exe`) или портативный архив (`GeForceNOWRichPresence-Windows.zip`) со страницы [Релизов (Releases)](https://github.com).
2. Запустите установщик и откройте приложение. Оно появится в системном трее.

### macOS
1. Скачайте архив `GeForceNOWRichPresence-macOS.zip`.
2. Распакуйте архив и запустите исполняемый файл.

### Linux
1. Скачайте архив `GeForceNOWRichPresence-Linux.tar.gz`.
2. Распакуйте файлы, сделайте бинарный файл исполняемым (`chmod +x GeForceNOWRichPresence`) и запустите его.

---

## 💻 Локальная компиляция и разработка

Если вы хотите запустить проект из исходного кода или скомпилировать его локально:

### 1. Требования
* Python 3.12+
* Google Chrome, Microsoft Edge или другой поддерживаемый браузер (для извлечения cookie)

### 2. Настройка виртуального окружения
```bash
# Клонировать репозиторий
git clone https://github.com
cd GeForce-NOW-Rich-Presence

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # На Windows: .\.venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt
pip install pyinstaller
```

### 3. Запуск из исходного кода
```bash
python -m src.GeForceNOWRichPresence
```

### 4. Локальная компиляция
Чтобы собрать автономный пакет с помощью PyInstaller, выполните:
```bash
pyinstaller --clean --noconfirm GeForceNOWRichPresence.spec
```
Готовый результат будет находиться в папке `dist/GeForceNOWRichPresence/`.

---

## 💬 О проекте и поддержка

Создано разработчиком [**KarmaDevz**](https://github.com), чтобы преодолеть ограничения облачного гейминга в профилях Discord.

⭐️ **Нравится проект?** Поставьте нам звезду на GitHub! Это очень помогает проекту стать заметнее!

<div align="center">
  <a href="https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/badge/Download%20Now%20➡️-1B5E20?style=for-the-badge&logo=nvidia&logoColor=white" alt="Download now"/>
  </a>
  <a href="https://paypal.me/KarmaDevz" target="_blank">
    <img src="https://img.shields.io/badge/💖%20Sponsor%20this%20Project-0070ba?style=for-the-badge&logo=paypal&logoColor=white" alt="Paypal Donations">
  </a>
</div>

<br/>

<div align="center">
  <h3>🆘 Нужна помощь?</h3>
  <p>Присоединяйтесь к официальному Discord-серверу <strong>GeForce NOW от Digevo</strong>, чтобы получить помощь и пообщаться с сообществом!</p>
  <a href="https://discord.gg/geforce-now-by-digevo-1412524071878525050">
    <img src="https://img.shields.io/badge/Join%20Discord%20Server-2962FF?style=for-the-badge&logo=discord&logoColor=white" alt="GeForce NOW by Digevo"/>
  </a>
</div>