"""HTTP endpoint for the iPhone Shortcut: POST a photo, get mom's verdict.

    uv run uvicorn app.server:app --host 0.0.0.0 --port 8787

Shortcut: Take Photo -> Get Contents of URL (POST, form, file field `photo`) -> Show Result.
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
import io

import qrcode
from typesafe_sdk import TypeSafeClient

from app.decide import decide
from app.modes import RECENT, bro, remember, wife

app = FastAPI(title="BroCheck")
_client = TypeSafeClient()

# The shared key is mine, so it gets a budget: per-IP and per-day. Bring your own key and there is no limit.
import json as _json
import os as _os
import time as _time
from collections import defaultdict

PER_IP_PER_DAY = int(_os.environ.get("PER_IP_PER_DAY", "10"))
GLOBAL_PER_DAY = int(_os.environ.get("GLOBAL_PER_DAY", "300"))
_USAGE = Path(__file__).resolve().parents[1] / "data" / "usage.json"
_usage = {"day": "", "total": 0, "ips": {}}
if _USAGE.exists():
    _usage = _json.loads(_USAGE.read_text())


def _client_for(key: str | None) -> tuple[TypeSafeClient, bool]:
    """(client, shared). A caller's own key bypasses the budget."""
    if key and key.strip():
        return TypeSafeClient(api_key=key.strip()), False
    return _client, True


def _charge(request: Request, shared: bool) -> None:
    if not shared:
        return
    day = _time.strftime("%Y-%m-%d")
    if _usage["day"] != day:
        _usage.update({"day": day, "total": 0, "ips": {}})
    ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    if _usage["total"] >= GLOBAL_PER_DAY:
        raise HTTPException(429, "Bro is tired. The shared key hit today's budget. Use your own TypeSafe key, or come back tomorrow.")
    if _usage["ips"].get(ip, 0) >= PER_IP_PER_DAY:
        raise HTTPException(429, f"Bro has judged {PER_IP_PER_DAY} times for you today. Use your own TypeSafe key for more.")
    _usage["total"] += 1
    _usage["ips"][ip] = _usage["ips"].get(ip, 0) + 1
    _USAGE.parent.mkdir(exist_ok=True)
    _USAGE.write_text(_json.dumps(_usage))


@app.get("/budget")
async def budget(request: Request):
    day = _time.strftime("%Y-%m-%d")
    ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    used = _usage["ips"].get(ip, 0) if _usage["day"] == day else 0
    total = _usage["total"] if _usage["day"] == day else 0
    return {"you_left": max(0, PER_IP_PER_DAY - used), "all_left": max(0, GLOBAL_PER_DAY - total)}


@app.post("/decide")
async def decide_photo(request: Request, photo: UploadFile = File(...), x_typesafe_key: str | None = Header(default=None)):
    client, shared = _client_for(x_typesafe_key)
    _charge(request, shared)
    suffix = Path(photo.filename or "p.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(await photo.read())
        path = Path(f.name)
    try:
        v = decide(path, client)
        out = {**v.__dict__, "mom": v.mom_says()}
        remember("mom", path, out)
    finally:
        path.unlink(missing_ok=True)
    return JSONResponse(out)


@app.post("/bro")
async def bro_photo(request: Request, me: UploadFile = File(...), them: UploadFile = File(...), x_typesafe_key: str | None = Header(default=None)):
    client, shared = _client_for(x_typesafe_key)
    _charge(request, shared)
    paths = []
    for up in (me, them):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(await up.read())
            paths.append(Path(f.name))
    try:
        out = bro(paths[0], paths[1], client)
        remember("bro", paths[1], out, paths[0])
    finally:
        for p in paths:
            p.unlink(missing_ok=True)
    return JSONResponse(out)


@app.post("/wife")
async def wife_photo(request: Request, photo: UploadFile = File(...), x_typesafe_key: str | None = Header(default=None)):
    client, shared = _client_for(x_typesafe_key)
    _charge(request, shared)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(await photo.read())
        path = Path(f.name)
    try:
        out = wife(path, client)
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
