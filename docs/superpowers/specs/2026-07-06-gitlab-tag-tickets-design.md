# Извлечение тикетов из GitLab по тегу

Дата: 2026-07-06

## Проблема

Сейчас тикеты извлекаются только из строк коммитов, которые пользователь
вставляет вручную (textarea в шаге 1 визарда / позиционные аргументы CLI).
`extract_jira_tickets()` прогоняет regex `[A-Z]+-\d+` по этим строкам.

Нужен второй режим: пользователь указывает **один тег** релиза
(например `26.1.0-rc7`), а инструмент сам тянет коммиты из GitLab между этим
тегом и предыдущим, извлекает из них тикеты и продолжает обычный поток
(JIRA → смена статусов/исполнителей → Telegram).

## Решения (зафиксированы)

- Источник репозитория: **GitLab REST API** (не локальный git, не clone).
- Проект (project id/path): **фиксирован в настройках**, не вводится per-релиз.
- Диапазон: **между двумя тегами** через compare API.
- Пользователь передаёт только `to`-тег; `from` вычисляется автоматически.
- Определение предыдущего тега: **по semver/числу** (собственная сортировка).
- Формат тегов: `MAJOR.MINOR.PATCH-rcN`, например `26.1.0-rc7`.
- Ручная вставка коммитов **сохраняется**; новый режим добавляется рядом
  (переключатель в шаге 1). Текущий функционал не ломается.
- Если у переданного тега нет предыдущего (он самый ранний) → **ошибка
  пользователю**, без фолбэка «от начала истории».

## Архитектура

### `core/gitlab_client.py` (новый модуль)

Framework-agnostic, по аналогии с `core/jira_client.py`. HTTP через `requests`
(уже в зависимостях). Заголовок `PRIVATE-TOKEN: <gitlab_token>`.

- `list_tags(cfg) -> list[str]`
  GET `/api/v4/projects/:id/repository/tags` (id — URL-encoded `gitlab_project`).
  Возвращает имена тегов. Пагинация: тянуть страницы пока не кончатся
  (per_page=100), т.к. тегов может быть > 20 (дефолт GitLab).

- `previous_tag(tags: list[str], target: str) -> str`
  Чистая функция. Парсит каждый тег regex `(\d+)\.(\d+)\.(\d+)-rc(\d+)` в
  кортеж `(major, minor, patch, rc)`. Теги, не подходящие под шаблон,
  игнорируются. Сортирует по кортежу. Находит `target`, возвращает ближайший
  меньший. Если `target` не найден среди распарсенных или предыдущего нет →
  `ValueError` (обрабатывается вызывающим слоем как ошибка пользователю).
  Сортировка кортежей автоматически покрывает границу релизов: предыдущий у
  `26.1.0-rc1` = последний rc прошлого релиза.

- `compare(cfg, from_tag, to_tag) -> list[str]`
  GET `/api/v4/projects/:id/repository/compare?from=<from_tag>&to=<to_tag>`.
  Из ответа берёт `commits[].title` (первая строка сообщения коммита) — по
  одной строке на коммит. Эти строки — вход для `extract_jira_tickets()`.

- `commits_for_tag(cfg, target) -> tuple[str, str, list[str]]`
  Оркестратор: `list_tags` → `previous_tag` → `compare`.
  Возвращает `(from_tag, to_tag, commits)` — from/to нужны UI для показа
  «какой диапазон посчитан».

### `core/config.py`

Три новых поля в `Config`: `gitlab_host`, `gitlab_token`, `gitlab_project`.
Резолв тем же паттерном (settings.json → env-фолбэк):
`GITLAB_HOST`, `GITLAB_TOKEN`, `GITLAB_PROJECT`.

`is_valid()` **не меняется** — GitLab опционален: ручной режим работает без
него. Отдельный хелпер `gitlab_ready()` (все три поля заполнены) для UI, чтобы
показывать/прятать GitLab-режим.

### UI: `app/api.py`

- `_config_from()` — добавить чтение трёх новых полей.
- Новый метод `fetch_from_gitlab(tag: str) -> dict`:
  1. `load_config()`, проверка `gitlab_ready()` → иначе `{"error": "gitlab_config"}`.
  2. `gitlab_client.commits_for_tag(cfg, tag)` в try/except:
     - `ValueError` (нет предыдущего тега) → `{"error": "no_previous_tag"}`.
     - сетевые/HTTP ошибки → `{"error": "gitlab_fetch", "detail": ...}`.
  3. Дальше тот же путь, что `parse_and_fetch`: `extract_jira_tickets(commits)`
     → connect JIRA → `find_issues` → тот же формат ответа, плюс поля
     `from_tag`, `to_tag` для показа диапазона.
  Общую часть с `parse_and_fetch` (extract → jira connect → find_issues →
  формирование ответа) вынести в приватный хелпер `_fetch_tickets(cfg, commits)`,
  чтобы оба метода её переиспользовали.

### UI: `app/web/` (index.html / app.js / style.css)

- Шаг 1: переключатель режима **«Из GitLab по тегу»** / **«Вставить вручную»**.
- GitLab-режим: поле ввода тега + кнопка «Загрузить». После загрузки — показ
  вычисленного `from → to` над списком тикетов.
- Ручной режим: textarea как сейчас, без изменений.
- Settings: новая секция **GitLab** (host / token / project) рядом с секциями
  JIRA / Telegram. Кнопка «Проверить» (тестовый `list_tags`) опционально.

### CLI: `release_notify.py`

- Позиционный `commits` сделать `nargs="*"` (был `+`).
- Новый опциональный флаг `--tag <tag>`.
- Если `--tag` задан: `gitlab_client.commits_for_tag(cfg, tag)` → его строки в
  `extract_jira_tickets`. Иначе — старое поведение по позиционным `commits`.
- Если ни `--tag`, ни `commits` не заданы → ошибка аргументов.

## Поток данных

```
tag "26.1.0-rc7"
  → list_tags(cfg)                → [все теги проекта]
  → previous_tag(tags, tag)       → "26.1.0-rc6"   (или ValueError)
  → compare(cfg, rc6, rc7)        → ["BugFix DEV-123 ...", ...]
  → extract_jira_tickets(commits) → ["DEV-123", ...]   (существующий код)
  → find_issues → change_status → change_assignee → build_message → send
```

## Обработка ошибок

| Ситуация | Поведение |
|---|---|
| GitLab не сконфигурирован | UI не даёт войти в GitLab-режим; api → `gitlab_config` |
| Нет предыдущего тега | `ValueError` → UI показывает «нет предыдущего тега» |
| Тег не найден в проекте | `ValueError` → та же ошибка пользователю |
| Сеть/HTTP/401 | `{"error": "gitlab_fetch", "detail": ...}` |
| Коммиты есть, тикетов нет | как сейчас — `no_tickets` |

## Тесты (`tests/`)

- `test_gitlab_client.py`:
  - `previous_tag`: обычный случай, граница релизов, единственный тег
    (`ValueError`), тег отсутствует (`ValueError`), мусорные теги игнорируются,
    порядок входного списка не важен.
  - `list_tags` / `compare`: замоканный `requests` (пагинация, парсинг commits).
  - `commits_for_tag`: оркестрация на моках.
- `test_config.py`: резолв трёх новых полей (settings.json и env-фолбэк),
  `gitlab_ready()`, `is_valid()` без изменений.

## Вне scope

- Локальный git / clone по URL / другие хостинги (GitHub, Bitbucket).
- Автовыбор проекта per-релиз.
- Фолбэк «от начала истории» при отсутствии предыдущего тега.
