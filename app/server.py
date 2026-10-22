"""HTTP endpoint for the iPhone Shortcut: POST a photo, get mom's verdict.

    uv run uvicorn app.server:app --host 0.0.0.0 --port 8787

Shortcut: Take Photo -> Get Contents of URL (POST, form, file field `photo`) -> Show Result.
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
import io

import qrcode
from typesafe_sdk import TypeSafeClient

from app.decide import decide
from app.modes import RECENT, bro, remember, wife

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
        out = {**v.__dict__, "mom": v.mom_says()}
        remember("mom", path, out)
    finally:
        path.unlink(missing_ok=True)
    return JSONResponse(out)


@app.post("/bro")
async def bro_photo(me: UploadFile = File(...), them: UploadFile = File(...)):
    paths = []
    for up in (me, them):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(await up.read())
            paths.append(Path(f.name))
    try:
        out = bro(paths[0], paths[1], _client)
        remember("bro", paths[1], out, paths[0])
    finally:
        for p in paths:
            p.unlink(missing_ok=True)
    return JSONResponse(out)


@app.post("/wife")
async def wife_photo(photo: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(await photo.read())
        path = Path(f.name)
    try:
        out = wife(path, _client)
        remember("wife", path, out)
    finally:
        path.unlink(missing_ok=True)
    return JSONResponse(out)


@app.get("/recent")
async def recent():
    return JSONResponse(list(RECENT))


def lan_url() -> str:
    """Address other phones on this Wi-Fi can reach. Prefer the Wi-Fi interface (en0): the
    default route here goes through WARP (100.96.x.x), which nobody else can reach."""
    import os
    import subprocess

    if os.environ.get("PUBLIC_URL"):  # e.g. a Cloudflare quick tunnel when the venue Wi-Fi isolates clients
        return os.environ["PUBLIC_URL"].rstrip("/") + "/"
    for iface in ("en0", "en1"):
        r = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return f"http://{r.stdout.strip()}:8787/"
    return "http://127.0.0.1:8787/"


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
