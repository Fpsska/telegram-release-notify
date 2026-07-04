# release-notify

Инструмент для отправки уведомлений о релизе в Telegram-чат. Автоматически извлекает Jira-тикеты из коммитов, получает их информацию через JIRA API, меняет статусы и исполнителей, затем отправляет сообщение со ссылками. Доступен как desktop-приложение (мастер из 3 шагов) и как CLI-скрипт.

## Как это работает

1. Из списка коммитов извлекаются номера Jira-тикетов (например, `DEV-12345`)
2. Для каждого тикета получается информация через JIRA API (заголовок, статус, reporter)
3. В зависимости от типа тикета меняется статус используя `core/workflow_matrix.json`:
   - **Bug** → `DEV Ready For Testing`
   - **Task/Sub-task/Improvement** → `Testing`
4. Меняется исполнитель (assignee):
   - Если reporter в списке тестировщиков → назначается на reporter
   - Иначе → назначается на QA lead
5. Сообщение формируется и отправляется в Telegram-чат

## Требования

- Python 3.10+
- Доступ к JIRA API (username/password)
- Telegram бот с токеном

## Desktop app

Скачай сборку из [Releases](../../releases) (или собери: см. Building) и запусти:

- **Windows**: `ReleaseNotify-windows.exe`
- **macOS**: `ReleaseNotify-macos-arm64.zip` (Apple Silicon) или `ReleaseNotify-macos-intel.zip` (Intel) — распакуй и запусти `ReleaseNotify.app`

При первом запуске заполни настройки (⚙): Telegram, JIRA, команда QA.
Настройки хранятся в `%APPDATA%\release-notify\settings.json` (Windows) или `~/.config/release-notify/settings.json` (macOS).

### macOS: первый запуск

Приложение не подписано, Gatekeeper заблокирует обычный двойной клик. Один раз:
правый клик по `ReleaseNotify.app` → «Открыть» → «Открыть» в диалоге. Либо в терминале:

```bash
xattr -d com.apple.quarantine /путь/до/ReleaseNotify.app
```

## CLI

```bash
pip install -r requirements.txt
python release_notify.py QA 26.1.0 7 \
  "abc12345(BugFix DEV-12345 Fix something)"
```

Конфиг CLI: тот же `settings.json`, при его отсутствии — `.env` (см. `.env.example`).

| Параметр      | Описание |
|---------------|----------|
| `environment` | Название среды, на которую деплоится релиз (например, `QA`, `PROD`) |
| `release`     | Версия релиза (например, `26.1.0`) |
| `rc`          | Номер release candidate |
| `commit...`   | Один или несколько коммитов в формате `hash(Type TICKET-123 Description)` |

Пример запуска скрипта:

```bash
python release_notify.py QA 26.1.0 7 \
  "abc12345(BugFix DEV-12345 Fix something)" \
  "def67890(BugFix DEV-67890 Fix something else)"
```

Скрипт:
1. Извлечёт тикеты DEV-12345 и DEV-67890
2. Получит их информацию через JIRA API
3. Поменяет статусы и assignee
4. Отправит сообщение в Telegram

### Переменные окружения (fallback, если нет settings.json)

| Переменная         | Описание |
|--------------------|----------|
| `BOT_TOKEN`        | Токен Telegram-бота (от [@BotFather](https://t.me/BotFather)) |
| `CHAT_ID`          | ID чата/группы куда отправлять сообщение |
| `JIRA_HOST`        | Хост Jira (например, `jira.yourcompany.com`) |
| `JIRA_USERNAME`    | Username для JIRA API |
| `JIRA_PASSWORD`    | Password для JIRA API |
| `JIRA_QA_TESTERS`  | Usernames тестировщиков через запятую (например, `user1,user2,user3`) |
| `JIRA_QA_LEAD`     | Username QA lead для назначения если reporter не в списке тестировщиков |
| `TELEGRAM_PROXY`   | Прокси для запросов к Telegram API (необязательно). Формат: `socks5://user:pass@host:port` или `http://user:pass@host:port` |

## Building

```bash
pip install -r requirements-dev.txt
python -m PyInstaller build.spec --noconfirm
# Windows: dist/ReleaseNotify.exe
# macOS:   dist/ReleaseNotify.app
```

PyInstaller не кросс-компилирует: сборка под Windows делается на Windows, под macOS — на macOS.

CI (`.github/workflows/build.yml`) собирает все три варианта (Windows, macOS arm64, macOS Intel) на каждый пуш в `main`; при пуше тега `v*` публикует их в GitHub Releases:

```bash
git tag v1.1.0 && git push origin v1.1.0
```

## Development

```bash
pip install -r requirements-dev.txt
python -m app.main    # UI из исходников
python -m pytest      # тесты
```

## Пример сообщения в Telegram

```
📋 На QA 26.1.0-rc7:
DEV-12345 - Fix null pointer exception in payment flow
DEV-67890 - Update user profile page layout
```

Каждый тикет — кликабельная ссылка на соответствующую задачу в Jira.

## Структура проекта

```
.
├── release_notify.py       # тонкий CLI поверх core/
├── core/
│   ├── config.py            # Config, settings.json (%APPDATA%) / .env fallback
│   ├── tickets.py            # извлечение тикетов из коммитов
│   ├── jira_client.py        # JIRA API, BFS по workflow_matrix, статусы, исполнители
│   ├── telegram.py           # сборка и отправка сообщения в Telegram
│   ├── resources.py          # пути к ресурсам (исходники / PyInstaller)
│   └── workflow_matrix.json  # матрица переходов между статусами
├── app/
│   ├── main.py                # запуск pywebview-окна
│   ├── api.py                 # js_api мост между UI и core/
│   └── web/                   # HTML/CSS/JS мастера (3 шага + настройки)
├── tests/                     # pytest
├── build.spec                  # PyInstaller-сборка (.exe на Windows, .app на macOS)
├── requirements.txt             # рантайм-зависимости (CLI + UI)
├── requirements-dev.txt         # + pytest, pyinstaller
├── .env.example                 # шаблон .env (fallback-конфиг)
└── README.md
```

## Workflow Matrix

Файл `core/workflow_matrix.json` содержит матрицу возможных переходов между статусами для каждого типа тикета (Bug, Task, Sub-task, Improvement).

Структура:
```json
{
  "Bug": {
    "текущий_статус": {
      "целевой_статус": "название_transition"
    }
  }
}
```

Скрипт использует BFS для поиска кратчайшего пути от текущего статуса к целевому и проходит по цепочке переходов.
