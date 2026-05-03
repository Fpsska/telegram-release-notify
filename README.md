# release-notify

Скрипт для отправки уведомлений о релизе в Telegram-чат. Автоматически извлекает Jira-тикеты из коммитов, получает их заголовки и формирует сообщение со ссылками.

## Как это работает

1. Из списка коммитов извлекаются номера Jira-тикетов (например, `DEV-12345`)
2. Открывается браузер — при необходимости пользователь логинится в Jira (SSO/SAML)
3. Для каждого тикета получается заголовок
4. Сообщение отправляется в Telegram-чат

## Требования

- Python 3.11+
- [Playwright](https://playwright.dev/python/) с браузером Chromium

## Установка

```bash
pip install requests playwright python-dotenv
playwright install chromium
```

## Настройка

Скопируй `.env.example` в `.env` и заполни значения:

```bash
cp .env.example .env
```

| Переменная  | Описание |
|-------------|----------|
| `BOT_TOKEN` | Токен Telegram-бота (от [@BotFather](https://t.me/BotFather)) |
| `CHAT_ID`   | ID чата/группы куда отправлять сообщение |
| `JIRA_HOST` | Хост Jira (например, `jira.yourcompany.com`) |

## Использование

```bash
python release_notify.py <environment> <release> <rc> <commit1> [commit2 ...]
```

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

При первом запуске (или если сессия истекла) откроется браузер — залогинься в Jira. После этого скрипт продолжит работу автоматически.

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
├── release_notify.py     # основной скрипт
├── .env                  # секреты (не коммитится)
├── .env.example          # шаблон .env
├── .gitignore
└── browser_session/      # сохранённая сессия браузера (не коммитится)
```
