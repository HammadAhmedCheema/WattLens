import asyncio
import httpx
import pytest
from app import ai_client
from app.schemas import ApplianceExtraction, Transcription

def transport_mock(monkeypatch,handler):
    real=httpx.AsyncClient
    monkeypatch.setattr(ai_client.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))

def test_invalid_json_retry(monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'choices':[{'message':{'content':'not-json' if len(calls)==1 else '{"category":"fan","rated_power_w":70}'}}]})
    transport_mock(monkeypatch,handler)
    output=asyncio.run(ai_client.chat(ApplianceExtraction,'data'))
    assert len(calls)==2 and output.rated_power_w==70

def test_twice_invalid(monkeypatch):
    calls=[]
    def handler(req):
        calls.append(1);return httpx.Response(200,json={'choices':[{'message':{'content':'invalid'}}]})
    transport_mock(monkeypatch,handler)
    with pytest.raises(ai_client.AIError):asyncio.run(ai_client.chat(ApplianceExtraction,'data'))
    assert len(calls)==2

def test_timeout(monkeypatch):
    def handler(req):raise httpx.ReadTimeout('timeout',request=req)
    transport_mock(monkeypatch,handler)
    with pytest.raises(ai_client.AIError,match='timed out'):asyncio.run(ai_client.chat(ApplianceExtraction,'data'))

def test_request_contract_and_image(monkeypatch):
    import json
    payloads=[]
    def handler(req):
        payloads.append(json.loads(req.content));return httpx.Response(200,json={'choices':[{'message':{'content':'{"visible_text":["fan"]}'}}]})
    transport_mock(monkeypatch,handler)
    asyncio.run(ai_client.chat(Transcription,'read',image=b'example'))
    p=payloads[0]
    assert p['model']=='qwen/qwen3-vl-8b-instruct' and p['stream'] is False and p['temperature']==0
    assert p['messages'][1]['content'][1]['image_url']['url']=='data:image/jpeg;base64,ZXhhbXBsZQ=='
    assert payloads and p['response_format']=={'type':'json_object'}

def test_config_exact_cloud_model():
    from app.config import Settings
    with pytest.raises(ValueError):Settings(model_name='oversized:99b')
    assert Settings().api_url=='https://openrouter.ai/api/v1/chat/completions'
    assert 'api_key' not in repr(Settings(api_key='secret'))

@pytest.mark.parametrize('status,phrase',[(401,'rejected'),(402,'credits'),(429,'rate limit'),(503,'unavailable')])
def test_api_errors_do_not_leak_credentials(monkeypatch,status,phrase):
    transport_mock(monkeypatch,lambda req:httpx.Response(status,json={'error':{'message':'test-key'}}))
    with pytest.raises(ai_client.AIError,match=phrase) as error:
        asyncio.run(ai_client.chat(Transcription,'read'))
    assert 'test-key' not in str(error.value)

def test_missing_key_never_calls_api(monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(ai_client,'settings',replace(ai_client.settings,api_key=''))
    with pytest.raises(ai_client.AIError,match='missing'):
        asyncio.run(ai_client.chat(Transcription,'read'))
