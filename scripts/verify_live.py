"""Explicit paid OpenRouter P0 smoke test using only bundled synthetic images.
Run manually, never in the default unit suite. Uses a disposable database.
"""
import json
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db import get_session
from app.models import Household
from app.config import ROOT, settings
from app.brief import number_guard

engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
SQLModel.metadata.create_all(engine)
with Session(engine) as session:
    session.add(Household(id=1)); session.commit()
def sessions():
    with Session(engine) as session: yield session
app.dependency_overrides[get_session] = sessions
client = TestClient(app)
report = {'model':settings.model_name,'provider':'openrouter','samples':'bundled synthetic images','steps':[]}
def record(name, started, fields=None):
    row={'step':name,'seconds':round(time.monotonic()-started,2),'passed':True}
    if fields: row['fields']=fields
    report['steps'].append(row); print(json.dumps(row),flush=True)
try:
    started=time.monotonic()
    with (ROOT/'samples'/'label.png').open('rb') as f:
        response=client.post('/appliances/extract',files={'files':('label.png',f,'image/png')},headers={'Accept':'application/json'})
    response.raise_for_status(); draft=response.json()['drafts'][0]
    assert draft['error'] is None, draft['error']
    fields=draft['fields']
    assert fields['rated_power_w']==70 and fields['voltage_v']==230 and fields['current_a']==0.4, fields
    assert fields['category']=='fan' and fields['model']=='DEMO-F70', fields
    assert client.get('/dashboard',headers={'Accept':'application/json'}).json()['appliances']==[]
    record('live_label_two_step_extraction',started,fields)
    response=client.post('/appliances',json={**fields,'name':'Synthetic fan','category':'fan','hours_per_day':8,
        'load_factor':1,'quantity':1,'source_image':draft['source_image'],'confirmed':True})
    response.raise_for_status(); aid=response.json()['id']
    assert client.get('/dashboard',headers={'Accept':'application/json'}).json()['estimated_total']==16.8
    started=time.monotonic()
    with (ROOT/'samples'/'bill.png').open('rb') as f:
        response=client.post('/bills/extract',files={'file':('bill.png',f,'image/png')},headers={'Accept':'application/json'})
    response.raise_for_status(); draft=response.json();fields=draft['fields']
    assert draft['error'] is None, draft['error']
    assert fields['units_kwh']==250 and fields['total_amount']==10000 and fields['billing_month']=='2026-10',fields
    record('live_bill_two_step_extraction',started,fields)
    response=client.post('/bills',json={**fields,'source_image':draft['source_image'],'confirmed':True})
    response.raise_for_status();bid=response.json()['id']
    started=time.monotonic()
    response=client.post('/analysis',json={'bill_id':bid},headers={'Accept':'application/json'})
    response.raise_for_status();analysis=response.json();numbers=analysis['numbers']
    assert numbers['gap_kwh']==233.2 and numbers['coverage_percent']==6.72 and numbers['avg_rate']==40,numbers
    assert analysis['brief_source']=='live_model',analysis['error']
    assert number_guard(analysis['brief'],numbers)
    assert len(analysis['brief']['findings'])==len(analysis['brief']['actions'])==3
    assert client.get('/analysis/'+str(analysis['id'])).status_code==200
    record('live_grounded_brief_and_saved_snapshot',started,analysis['brief'])
    for url in ['/','/dashboard','/bills','/analysis']:
        assert client.get(url).status_code==200,url
    report['passed']=True
finally:
    app.dependency_overrides.clear()
    (ROOT/'docs').mkdir(exist_ok=True)
    (ROOT/'docs'/'live-smoke-results.json').write_text(json.dumps(report,indent=2))
