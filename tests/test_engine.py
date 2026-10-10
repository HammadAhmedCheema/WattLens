import pytest
from app.engine import estimate_appliance, reconcile, audit, displayed

def test_tier_a_ignores_hours():
    row=estimate_appliance({'annual_kwh':360,'quantity':2,'hours_per_day':1})
    assert row['tier']=='A' and row['monthly_kwh']==60
    assert row['low_kwh']==51 and row['high_kwh']==69

def test_tier_b_and_approximation():
    row=estimate_appliance({'rated_power_w':70,'hours_per_day':8,'quantity':3})
    assert row['monthly_kwh']==pytest.approx(50.4) and row['tier']=='B'
    row=estimate_appliance({'voltage_v':230,'current_a':.4,'hours_per_day':8})
    assert row['monthly_kwh']==pytest.approx(22.08) and row['approximate_power']

def test_tier_c():
    row=estimate_appliance({'category':'fan'})
    assert row['tier']=='C' and row['placeholder'] and row['monthly_kwh']==16.8
    assert row['low_kwh']==8.4

@pytest.mark.parametrize('coverage,band',[(.79,'under_explained'),(.8,'good_match'),(1.2,'good_match'),(1.21,'over_estimated')])
def test_boundaries(coverage,band):
    assert reconcile(coverage*100,100)['band']==band

@pytest.mark.parametrize('bill',[None,0,-1])
def test_missing_or_zero(bill):
    r=reconcile(100,bill,2000)
    assert r['coverage'] is None and r['avg_rate'] is None and r['band']=='unavailable'

def test_cost_totals_and_ranking():
    r=audit([{'name':'small','rated_power_w':10,'hours_per_day':1},{'name':'big','annual_kwh':1200}],{'units_kwh':200,'total_amount':8000})
    assert r['appliances'][0]['name']=='big'
    assert r['estimated_total']==100.3 and r['avg_rate']==40
    assert r['appliances'][0]['estimated_cost']==4000

def test_rounding():
    assert displayed(1.005)==1.01
    assert displayed(None) is None
