import asyncio
from app.brief import number_guard, generate
from app.engine import audit
from app.schemas import BriefOutput
from app import ai_client

def test_guard_pass_and_fail():
    data={'monthly_kwh':1000.125,'gap':-20,'coverage_percent':80}
    assert number_guard('1,000.13 kWh, -20 kWh, 80%',data)
    assert not number_guard('Save 999 kWh',data)
    assert not number_guard('1000.125 kWh',data)
    assert not number_guard('1e9',data)
    assert number_guard('Estimates have uncertainty.',data)

def test_guard_rejects_then_falls_back(monkeypatch):
    calls=[]
    async def bad(*a,**kw):
        calls.append(1)
        return BriefOutput(headline='Save 99999 units',findings=['a','b','c'],actions=['a','b','c'])
    monkeypatch.setattr(ai_client,'chat',bad)
    output,source,error=asyncio.run(generate(audit([{'name':'Fan','rated_power_w':70,'hours_per_day':8}])))
    assert len(calls)==2 and source=='calculated_fallback' and error
    assert 'estimates' in ' '.join(output['caveats'])

def test_valid_brief(monkeypatch):
    async def good(*a,**kw):
        return BriefOutput(headline='Review the estimate',findings=['a','b','c'],actions=['a','b','c'])
    monkeypatch.setattr(ai_client,'chat',good)
    _,source,error=asyncio.run(generate(audit([])))
    assert source=='live_model' and error is None
