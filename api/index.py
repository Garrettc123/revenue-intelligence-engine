from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import os

app = FastAPI()

STRIPE_AUDIT_LINK = os.getenv("STRIPE_AUDIT_LINK", "https://buy.stripe.com/dRm8wPbb72pY2Mz8BR43S1D")

@app.get("/", response_class=HTMLResponse)
async def root():
    return f"""<!DOCTYPE html><html><head><title>Garcar — AI Ops Audit</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:80px auto;padding:0 20px">
<h1>Garcar Enterprise</h1>
<p>Find out exactly where your business is leaking time and money.</p>
<p><strong>$47 Starter Audit</strong> — 5-page written report, 48-hour delivery, no retainer.</p>
<a href="{STRIPE_AUDIT_LINK}" style="display:inline-block;background:#000;color:#fff;padding:14px 28px;text-decoration:none;border-radius:4px;font-size:16px">Get the Audit — $47</a>
</body></html>"""

@app.get("/audit")
async def audit():
    return RedirectResponse(STRIPE_AUDIT_LINK, status_code=302)

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "live": True})

@app.get("/pricing")
async def pricing():
    return JSONResponse({"tiers": [
        {"name": "Starter Audit", "price": 47, "type": "one_time"},
        {"name": "Diagnostic Audit", "price": 497, "type": "one_time"},
        {"name": "Starter Retainer", "price": 997, "type": "monthly"},
        {"name": "Growth Retainer", "price": 2500, "type": "monthly"},
        {"name": "Enterprise", "price": 5000, "type": "monthly"},
        {"name": "Founding Pilot", "price": 10000, "type": "one_time"}
    ]})
