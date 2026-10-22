"""HTTP endpoint for the iPhone Shortcut: POST a photo, get mom's verdict.

    uv run uvicorn app.server:app --host 0.0.0.0 --port 8787

Shortcut: Take Photo -> Get Contents of URL (POST, form, file field `photo`) -> Show Result.
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
import io
import socket

import qrcode
from typesafe_sdk import TypeSafeClient

from app.decide import decide

app = FastAPI(title="Mama Approves")
_client = TypeSafeClient()


@app.post("/decide")
async def decide_photo(photo: UploadFile = File(...)):
    suffix = Path(photo.filename or "p.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(await photo.read())
        path = Path(f.name)
    try:
        v = decide(path, _client)
    finally:
        path.unlink(missing_ok=True)
    return JSONResponse({**v.__dict__, "mom": v.mom_says()})


def lan_url() -> str:
    """Address other phones on this Wi-Fi can reach: the Mac's LAN IP, not 127.0.0.1."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
    except OSError:
        ip = "127.0.0.1"
    return f"http://{ip}:8787/"


@app.get("/qr.png")
async def qr_png():
    img = qrcode.make(lan_url(), box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (Path(__file__).parent / "index.html").read_text()
    return html.replace("{{LAN_URL}}", lan_url())
