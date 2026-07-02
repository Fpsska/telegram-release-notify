import webview

from app.api import Api
from core.resources import resource_path


def main() -> None:
    api = Api()
    window = webview.create_window(
        "Release Notify",
        str(resource_path("app/web/index.html")),
        js_api=api,
        width=760, height=640, min_size=(640, 560),
        background_color="#1a1f27",
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
