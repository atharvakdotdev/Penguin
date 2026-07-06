"""WebView entry point for the Penguin app."""

import webview

from api import Api


api = Api()


def main():
    webview.create_window(
        title="Penguin",
        url="templates/index.html",
        width=1980,
        height=1080,
        js_api=api,
    )
    webview.start()


if __name__ == "__main__":
    main()