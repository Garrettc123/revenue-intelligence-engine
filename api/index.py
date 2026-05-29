from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import os

app = FastAPI()

STRIPE_LINK = os.getenv("STRIPE_AUDIT_LINK", "https://buy.stripe.com/dRm8wPbb72pY2Mz8BR43S1D")

@app.get("/", response_class=HTMLResponse)
async def root():
    html = f"""<!DOCTYPE html>
<html><head><title>Garcar Enterprise</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#0f0f0f;color:#e8e8e8;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}}
.wrap{{max-width:640px;text-align:center}}
h1{{font-size:clamp(2rem,6vw,3.5rem);font-weight:700;margin-bottom:1rem;letter-spacing:-0.02em}}
p{{font-size:1.125rem;color:#999;line-height:1.7;margin-bottom:2rem;max-width:48ch;margin-inline:auto}}
.cta{{display:inline-block;background:#01696f;color:#fff;padding:1rem 2.5rem;border-radius:8px;text-decoration:none;font-size:1.125rem;font-weight:600;transition:background .2s}}
.cta:hover{{background:#0c4e54}}
.sub{{margin-top:1.5rem;font-size:.875rem;color:#666}}
</style>
</head>
<body>
<div class="wrap">
<h1>Garcar Enterprise</h1>
<p>AI-powered autonomous business automation. From lead intake to invoice — zero humans required.</p>
<a class="cta" href="{STRIPE_LINK}">Get Your Starter Audit — $47</a>
<p class="sub">48-hour turnaround · No fluff · Ranked automation roadmap</p>
</div>
</body></html>"""
    return html

@app.get("/audit")
async def audit():
    return RedirectResponse(url=STRIPE_LINK, status_code=302)

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "garcar-landing", "version": "3.1.0"})

@app.get("/pricing")
async def pricing():
    tiers = [
        {"name": "Starter Audit", "price": 47, "type": "one_time"},
        {"name": "Diagnostic", "price": 497, "type": "one_time"},
        {"name": "Starter Retainer", "price": 997, "type": "monthly"},
        {"name": "Growth", "price": 2500, "type": "monthly"},
        {"name": "Enterprise", "price": 5000, "type": "monthly"},
        {"name": "Founding Pilot", "price": 10000, "type": "one_time"}
    ]
    return JSONResponse({"tiers": tiers})

@app.post("/webhook")
async def webhook(request: Request):
    return JSONResponse({"received": True})
