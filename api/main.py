"""
GARCAR REVENUE INTELLIGENCE ENGINE — FastAPI Layer v3.1
Full-stack node: exposes /health /run /status /proofs /ui /sync
PLATFORM_STANDARD v1.1 compliant
"""

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import os, json, uuid
from datetime import datetime, timezone

sys_path_fix = __import__('sys'); sys_path_fix.path.insert(0, '..')
from engine import RHNSRevenueEngine

app = FastAPI(
    title="Revenue Intelligence Engine",
    description="Garcar RHNS full-stack revenue node v3.1",
    version="3.1.0",
)

engine = RHNSRevenueEngine()
security = HTTPBearer(auto_error=False)
GARCAR_API_KEY = os.getenv('GARCAR_API_KEY', 'dev-key')


def verify_token(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if GARCAR_API_KEY == 'dev-key':
        return True
    if not creds or creds.credentials != GARCAR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


class RunRequest(BaseModel):
    type: str
    source: str = 'stripe'
    value_usd: float = 0.0
    metadata: dict = {}


@app.get('/health')
def health():
    return {
        'status': 'ok',
        'system_id': 'revenue-intelligence-engine',
        'version': '3.1.0',
        'platform_standard': 'GARCAR-STD-1.1',
        'mastered': engine._mastered,
        'mastery_streak': engine._mastery_streak,
        'sync_sources': engine.sync.status(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.post('/run', dependencies=[Depends(verify_token)])
def run(req: RunRequest):
    result = engine.run_cycle(req.dict())
    return result


@app.post('/batch', dependencies=[Depends(verify_token)])
def batch(events: list[RunRequest]):
    return engine.run_batch([e.dict() for e in events])


@app.post('/sync', dependencies=[Depends(verify_token)])
def sync_cycle(background_tasks: BackgroundTasks):
    """
    Trigger a full autonomous multi-source sync cycle.
    Polls Stripe, HubSpot, Shopify, Linear — deduplicates, boosts confidence,
    runs each signal through the full RHNS pipeline.
    """
    result = engine.run_synced_cycle()
    return result


@app.get('/status', dependencies=[Depends(verify_token)])
def status():
    mem_stats = engine.memory.stats()
    return {
        'system_id': 'revenue-intelligence-engine',
        'version': '3.1.0',
        'signals_processed': len(engine.proofs),
        'mastered': engine._mastered,
        'mastery_streak': engine._mastery_streak,
        'mastery_threshold': engine.MASTERY_THRESHOLD,
        'mastery_streak_required': engine.MASTERY_STREAK_REQUIRED,
        'dag_available': engine.dag is not None,
        'memory': mem_stats,
        'sync_sources': engine.sync.status(),
    }


@app.get('/proofs', dependencies=[Depends(verify_token)])
def proofs(limit: int = 50):
    from dataclasses import asdict
    return [asdict(p) for p in engine.proofs[-limit:]]


@app.get('/memory', dependencies=[Depends(verify_token)])
def memory_stats():
    return engine.memory.stats()


@app.get('/ui', response_class=HTMLResponse)
def ui():
    return HTMLResponse(content=_dashboard_html(), status_code=200)


def _dashboard_html() -> str:
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revenue Intelligence Engine</title>
<style>
  :root{--bg:#171614;--surface:#1c1b19;--text:#cdccca;--primary:#4f98a3;--success:#6daa45;--error:#d163a7;--border:#393836;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{background:var(--bg);color:var(--text);font-family:\'Inter\',system-ui,sans-serif;padding:2rem;}
  h1{color:var(--primary);font-size:1.5rem;margin-bottom:1rem;}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:.5rem;padding:1.25rem;margin-bottom:1rem;}
  .label{font-size:.75rem;color:#797876;text-transform:uppercase;letter-spacing:.05em;}
  .value{font-size:1.25rem;font-weight:600;margin-top:.25rem;}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem;}
  .ok{color:var(--success);} .warn{color:var(--error);}
  button{background:var(--primary);color:#fff;border:none;border-radius:.375rem;padding:.5rem 1rem;cursor:pointer;font-size:.875rem;margin-right:.5rem;}
  button:hover{opacity:.85;}
  button.sync{background:#7c5cbf;}
  pre{background:#0d0c0b;border-radius:.375rem;padding:1rem;font-size:.75rem;overflow:auto;max-height:300px;}
</style>
</head>
<body>
<h1>⚡ Revenue Intelligence Engine v3.1</h1>
<div class="grid" id="stats"></div>
<div class="card">
  <div class="label">Run Test Event</div>
  <select id="evType" style="margin:.5rem 0;padding:.375rem;background:#0d0c0b;color:var(--text);border:1px solid var(--border);border-radius:.375rem;">
    <option value="payment_intent.payment_failed">payment_intent.payment_failed</option>
    <option value="customer.subscription.deleted">customer.subscription.deleted</option>
    <option value="payment_intent.succeeded">payment_intent.succeeded</option>
    <option value="invoice.upcoming">invoice.upcoming</option>
  </select><br>
  <input id="evVal" type="number" placeholder="value_usd" value="299" style="padding:.375rem;background:#0d0c0b;color:var(--text);border:1px solid var(--border);border-radius:.375rem;margin-bottom:.5rem;">
  <br>
  <button onclick="runEvent()">Run Cycle</button>
  <button class="sync" onclick="runSync()">&#x21bb; Sync All Sources</button>
</div>
<div class="card">
  <div class="label">Last Result</div>
  <pre id="result">—</pre>
</div>
<script>
async function load(){
  const r=await fetch(\'\'/status\'\'  );const d=await r.json();
  const mem=d.memory||{};
  const src=d.sync_sources||{};
  document.getElementById(\'stats\').innerHTML=[
    [\'System ID\',d.system_id],
    [\'Version\',d.version],
    [\'Signals Processed\',d.signals_processed],
    [\'Mastery Streak\',d.mastery_streak+\' / \'+d.mastery_streak_required],
    [\'Mastered\',d.mastered?\'\u2705 YES\':\'\u23f3 NO\'],
    [\'DAG Online\',d.dag_available?\'\u2705\':\'\u26a0\ufe0f\'],
    [\'Memory Entries\',mem.total_entries||0],
    [\'Success Rate\',(((mem.success_rate||0)*100).toFixed(1)+\' %\')],
    [\'Stripe\',src.stripe?\'\u2705\':\'\u2014\'],
    [\'HubSpot\',src.hubspot?\'\u2705\':\'\u2014\'],
    [\'Shopify\',src.shopify?\'\u2705\':\'\u2014\'],
    [\'Linear\',src.linear?\'\u2705\':\'\u2014\'],
  ].map(([l,v])=>`<div class="card"><div class="label">${l}</div><div class="value">${v}</div></div>`).join(\'\');
}
async function runEvent(){
  const t=document.getElementById(\'evType\').value;
  const v=parseFloat(document.getElementById(\'evVal\').value)||0;
  const r=await fetch(\'/run\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({type:t,source:\'stripe\',value_usd:v,metadata:{}})});
  const d=await r.json();
  document.getElementById(\'result\').textContent=JSON.stringify(d,null,2);
  load();
}
async function runSync(){
  document.getElementById(\'result\').textContent=\'Syncing all sources...\';
  const r=await fetch(\'/sync\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'}});
  const d=await r.json();
  document.getElementById(\'result\').textContent=JSON.stringify(d,null,2);
  load();
}
load();
setInterval(load,10000);
</script>
</body>
</html>
'''
