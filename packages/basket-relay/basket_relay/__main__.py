"""Run relay server: python -m basket_relay [--host 0.0.0.0] [--port 7683]."""

import argparse
import asyncio
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Basket message relay server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=7683, help="Bind port")
    args = parser.parse_args()

    async def run() -> None:
        import uvicorn
        from .app import create_app
        app = create_app()
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
