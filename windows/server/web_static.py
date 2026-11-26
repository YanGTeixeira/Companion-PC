"""Arquivos do app web (pasta web/) e links temporários de download, pela mesma porta do WebSocket."""
from http import HTTPStatus
from pathlib import Path

from websockets.datastructures import Headers
from websockets.http11 import Response

import extras

WEB_DIR = Path(__file__).resolve().parent / "web"

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json",
        ".webmanifest": "application/manifest+json", ".png": "image/png", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".webm": "video/webm",
        ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


def web_build():
    """Muda quando algum arquivo do app web muda: o celular recarrega a página sozinho."""
    try:
        return int(max(f.stat().st_mtime for f in WEB_DIR.rglob("*") if f.is_file()))
    except (OSError, ValueError):
        return 0


def serve_static(connection, request):
    """Requisições HTTP comuns recebem os arquivos de web/; WebSocket segue normal."""
    if "websocket" in request.headers.get("Upgrade", "").lower():
        return None
    path = request.path.split("?", 1)[0].split("#", 1)[0]
    if path.startswith("/dl/"):  # arquivo do PC liberado por clip.get (link temporário)
        got = extras.dl_fetch(path)
        if not got:
            return connection.respond(HTTPStatus.NOT_FOUND, "link expirado\n")
        name, body, ctype = got
        from urllib.parse import quote
        headers = Headers([("Content-Type", ctype), ("Content-Length", str(len(body))),
                           ("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name)}"),
                           ("Cache-Control", "no-store")])
        return Response(200, "OK", headers, body)
    name = "index.html" if path in ("/", "") else "editor.html" if path.rstrip("/") == "/editor" else path.lstrip("/")
    f = (WEB_DIR / name).resolve()
    if WEB_DIR.resolve() not in f.parents or not f.is_file() or f.suffix not in MIME:
        return connection.respond(HTTPStatus.NOT_FOUND, "não encontrado\n")
    body = f.read_bytes()
    if f.suffix == ".html":
        # a página leva a versão do app: uma cópia velha (guardada pelo service worker enquanto o PC reiniciava)
        # percebe que está desatualizada no "welcome" e recarrega
        body = body.replace(b"</head>", f'<meta name="build" content="{web_build()}">\n</head>'.encode(), 1)
    headers = Headers([("Content-Type", MIME[f.suffix]), ("Content-Length", str(len(body))),
                       ("Cache-Control", "no-cache"), ("X-Content-Type-Options", "nosniff")])
    return Response(200, "OK", headers, body)
