"""HTTP endpoint for the iPhone Shortcut: POST a photo, get mom's verdict.

    uv run uvicorn app.server:app --host 0.0.0.0 --port 8787

Shortcut: Take Photo -> Get Contents of URL (POST, form, file field `photo`) -> Show Result.
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
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


@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!doctype html><meta name=viewport content="width=device-width">
<title>Mama Approves</title>
<body style="font:20px system-ui;max-width:28em;margin:2em auto;text-align:center">
<h1>Мама одобрит?</h1>
<form method=post action=/decide enctype=multipart/form-data id=f>
<input type=file name=photo accept="image/*" capture=environment onchange="go()" style="font-size:1.2em">
</form><pre id=o style="text-align:left;white-space:pre-wrap"></pre>
<script>
async function go(){const fd=new FormData(f);o.textContent='…';
const r=await fetch('/decide',{method:'POST',body:fd});const j=await r.json();
const m={APPROVE:'✅',NOPE:'❌',REVIEW:'🤔'}[j.decision];
o.textContent=`${m} ${j.decision}  mom=${j.approve}  conf=${j.confidence}  ${j.ms} ms\n«${j.mom}»\n\n`+JSON.stringify(j.answers,null,1)}
</script></body>"""
