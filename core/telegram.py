import requests

from .config import Config


def build_message(jira_host: str, environment: str, release: str, rc: str,
                  items: list[tuple[str, str]]) -> str:
    """items: [(ticket_key, summary), ...]"""
    lines = [f"\U0001f4cb На {environment} {release}-rc{rc}:"]
    for key, summary in items:
        url = f"https://{jira_host}/browse/{key}"
        safe = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'<a href="{url}">{key} - {safe}</a>')
    return "\n\n".join(lines)


def send_telegram(cfg: Config, message: str) -> tuple[bool, str]:
    """Возвращает (успех, текст ошибки)."""
    proxies = {"https": cfg.telegram_proxy} if cfg.telegram_proxy else None
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage",
            json={
                "chat_id": cfg.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            proxies=proxies,
            timeout=15,
        )
        if resp.ok:
            return True, ""
        return False, f"Telegram error: {resp.status_code} {resp.text}"
    except requests.exceptions.ConnectionError:
        return False, "Cannot reach api.telegram.org (network/proxy issue)."
    except requests.exceptions.Timeout:
        return False, "Telegram request timed out."
    except requests.exceptions.RequestException as e:
        return False, f"Telegram request failed: {e}"
