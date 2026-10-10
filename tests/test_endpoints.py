import io
import json
import httpx
import pytest
from PIL import Image
from app import ai_client
from app.schemas import Transcription, ApplianceExtraction, BillExtraction
from app.extraction import preprocess, MAX_BYTES

def photo():
    b=io.BytesIO();Image.new('RGB',(200,100),'white').save(b,format='PNG');return b.getvalue()

def test_extract_valid_and_not_saved(client,monkeypatch):
    async def mock(schema,*args,**kwargs):
        if schema==Transcription:return Transcription(visible_text=['70 W fan'])
        return ApplianceExtraction(category='fan',rated_power_w=70,field_status={'rated_power_w':'read'})
    monkeypatch.setattr(ai_client,'chat',mock)
    r=client.post('/appliances/extract',files={'files':('label.png',photo(),'image/png')},headers={'Accept':'application/json'})
    assert r.status_code==200
    draft=r.json()['drafts'][0]
    assert draft['fields']['rated_power_w']==70 and draft['source_image'].endswith('.jpg')
    assert client.get('/dashboard',headers={'Accept':'application/json'}).json()['appliances']==[]

def test_save_update_delete_manual_and_refresh(client):
    item={'name':'Fan','category':'fan','rated_power_w':70,'hours_per_day':8,'quantity':3}
    r=client.post('/appliances/manual',json=item);assert r.status_code==200
    aid=r.json()['id']
    d=client.get('/dashboard',headers={'Accept':'application/json'}).json()
    assert d['estimated_total']==50.4
    assert 'Fan' in client.get('/dashboard').text
    assert client.get(f'/appliances/{aid}/edit').status_code==200
    assert client.put(f'/appliances/{aid}',json={**item,'quantity':1}).status_code==200
    assert client.get('/dashboard',headers={'Accept':'application/json'}).json()['estimated_total']==16.8
    assert client.delete(f'/appliances/{aid}').status_code==200
    assert client.get('/dashboard',headers={'Accept':'application/json'}).json()['estimated_total']==0

@pytest.mark.parametrize('value',[0,-2])
def test_bad_quantity(client,value):
    assert client.post('/appliances',json={'name':'Fan','quantity':value}).status_code==422

def test_confirmation_and_source_validation(client):
    assert client.post('/appliances',json={'name':'fan','confirmed':False}).status_code==422
    assert client.post('/appliances',json={'name':'fan','source_image':'../../secret'}).status_code==422

def test_bill_and_snapshot(client,monkeypatch):
    client.post('/appliances',json={'name':'Fridge','category':'refrigerator','annual_kwh':360})
    bill=client.post('/bills',json={'billing_month':'2026-10','units_kwh':250,'total_amount':10000}).json()
    from app.routes import analysis
    from app.brief import fallback
    async def brief(output,demo):return fallback(output),'calculated_fallback',None
    monkeypatch.setattr(analysis,'generate',brief)
    r=client.post('/analysis',json={'bill_id':bill['id']},headers={'Accept':'application/json'})
    assert r.status_code==200 and r.json()['numbers']['gap_kwh']==220
    aid=r.json()['id']
    client.post('/appliances',json={'name':'New fan','rated_power_w':70})
    assert client.get(f'/analysis/{aid}').status_code==200
    assert '30.0' in client.get(f'/analysis/{aid}').text
    assert client.get('/bills').status_code==200
    assert client.get('/analysis').status_code==200

def test_bill_photo(client,monkeypatch):
    async def mock(schema,*args,**kwargs):
        if schema==Transcription:return Transcription(visible_text=['250 kWh','PKR 10000'])
        return BillExtraction(units_kwh=250,total_amount=10000)
    monkeypatch.setattr(ai_client,'chat',mock)
    r=client.post('/bills/extract',files={'file':('bill.webp',photo(),'image/webp')},headers={'Accept':'application/json'})
    assert r.status_code==200 and r.json()['fields']['units_kwh']==250
    assert client.get('/bills',headers={'Accept':'application/json'}).json()==[]

def test_timeout_draft(client,monkeypatch):
    async def fail(*args,**kw):raise ai_client.AIError('OpenRouter timed out.')
    monkeypatch.setattr(ai_client,'chat',fail)
    r=client.post('/appliances/extract',files={'files':('x.png',photo(),'image/png')},headers={'Accept':'application/json'})
    d=r.json()['drafts'][0]
    assert r.status_code==200 and d['error']=='OpenRouter timed out.'
    assert d['fields']['rated_power_w'] is None and set(d['fields']['field_status'].values())=={'unclear'}

def test_upload_bad_type_and_oversize(client):
    assert client.post('/appliances/extract',files={'files':('bill.pdf',b'%PDF','application/pdf')}).status_code==400
    assert client.post('/appliances/extract',files={'files':('huge.png',b'x'*(MAX_BYTES+1),'image/png')}).status_code==413
    assert client.post('/appliances/extract',files={'files':('fake.png',b'not image','image/png')}).status_code==400

def test_image_resize_and_metadata_removed():
    b=io.BytesIO();im=Image.new('RGB',(2000,1000),'white');exif=Image.Exif();exif[270]='synthetic metadata';im.save(b,format='JPEG',exif=exif)
    _,clean=preprocess(b.getvalue(),'test.jpg')
    result=Image.open(io.BytesIO(clean));assert result.size==(1536,768) and not result.getexif()

def test_demo_isolated_and_complete(client,monkeypatch):
    async def fail(*a,**kw):raise AssertionError('Demo must not call OpenRouter')
    monkeypatch.setattr(ai_client,'chat',fail)
    client.post('/mode',data={'mode':'demo'})
    page=client.get('/dashboard');assert page.status_code==200 and 'Demo Mode: saved model outputs' in page.text
    d=client.get('/dashboard',headers={'Accept':'application/json'}).json();assert len(d['appliances'])==5
    r=client.post('/analysis',json={},headers={'Accept':'application/json'});assert r.status_code==200 and r.json()['brief_source']=='saved_demo'
    r=client.post('/appliances/extract',files={'files':('x.png',photo(),'image/png')});assert r.status_code==200 and 'synthetic placeholder' in r.text
    client.post('/mode',data={'mode':'live'})
    assert client.get('/dashboard',headers={'Accept':'application/json'}).json()['appliances']==[]
    assert client.get('/analysis/'+str(r.status_code)).status_code==404

def test_all_forms_render(client):
    for path in ['/','/appliances/manual','/bills','/bills/manual','/dashboard','/analysis']:
        assert client.get(path).status_code==200,path

def test_invalid_model_json_retries_through_upload(client,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        content=['invalid','{"visible_text":["Rated input 70 W"]}','{"rated_power_w":70,"category":"fan"}'][len(calls)-1]
        return httpx.Response(200,json={'choices':[{'message':{'content':content}}]})
    real=httpx.AsyncClient
    monkeypatch.setattr(ai_client.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    r=client.post('/appliances/extract',files={'files':('label.png',photo(),'image/png')},headers={'Accept':'application/json'})
    assert r.status_code==200 and len(calls)==3
    assert r.json()['drafts'][0]['fields']['rated_power_w']==70

def test_live_cloud_disclosure_and_safe_health(client):
    assert 'Live uploads are sent to OpenRouter' in client.get('/').text
    data=client.get('/healthz').json()
    assert data['provider']=='openrouter' and data['connectivity_tested'] is False
    assert 'api_key' not in data
