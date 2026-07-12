import argparse

import uvicorn

from .app import create_app
from .core.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Merida final-app API.")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    settings = Settings()

    if args.reload:
        uvicorn.run(
            "merida_api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=True,
        )
        return

    uvicorn.run(
        create_app(settings, require_dashboard=True),
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
