"""Entry point: ``python main.py`` or ``uvicorn main:app``."""

from __future__ import annotations

from shopper.api import create_app
from shopper.settings import get_settings

app = create_app()


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run("main:app", host=s.host, port=s.port)


if __name__ == "__main__":
    main()
