import os

import uvicorn

from td_plugin_api.app import app


def main() -> None:
    """Serves the API on `TD_PLUGIN_API_HOST` and `TD_PLUGIN_API_PORT`."""
    uvicorn.run(
        app,
        host=os.getenv("TD_PLUGIN_API_HOST", "127.0.0.1"),
        port=int(os.getenv("TD_PLUGIN_API_PORT", "8700")),
    )


if __name__ == "__main__":
    main()
