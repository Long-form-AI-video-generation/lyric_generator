"""Simple static server for the lyric visualizer frontend."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    """Serve the visualizer directory on a local development port."""
    root = Path(__file__).resolve().parent
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *args,
        directory=str(root),
        **kwargs,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 8000), handler)
    print("Visualizer available at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
