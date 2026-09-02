"""WebView entry point for the Penguin app."""

from pathlib import Path

import webview

from api import Api

api = Api(None)

def main():
    index_path = Path(__file__).resolve().parent / "templates" / "index.html"

    window = webview.create_window(
        title="Penguin",
        url=index_path.as_uri(),
        width=1980,
        height=1080,
        js_api=api,
    )

    api.windowobj = window

    webview.start()


if __name__ == "__main__":
    main()