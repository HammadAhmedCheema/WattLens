"""Pure energy calculations. No model calls, I/O or mutable global state."""
import math
from decimal import Decimal, ROUND_HALF_UP
from .defaults import DEFAULTS

def displayed(value, places=2):
    if value is None: return None
    if not math.isfinite(float(value)): raise ValueError('Finite numbers required.')
    return float(Decimal(str(value)).quantize(Decimal('1').scaleb(-places), rounding=ROUND_HALF_UP))

def estimate_appliance(a: dict) -> dict:
    category = a.get('category') or 'other'
    default = DEFAULTS.get(category, DEFAULTS['other'])
    quantity = a.get('quantity', 1)
    hours = a.get('hours_per_day', default['hours'])
    factor = a.get('load_factor', default['load_factor'])
    if quantity < 1 or not 0 <= hours <= 24 or not 0 <= factor <= 1:
        raise ValueError('Invalid usage inputs.')
    annual, power = a.get('annual_kwh'), a.get('rated_power_w')
    approximate = False
    if annual is not None:
        energy = annual / 12 * quantity
        tier, band, basis = 'A', .15, 'Annual label kWh ÷ 12; label usage assumptions apply'
        assumptions = {'quantity': quantity, 'annual_kwh': annual, 'range_percent': 15}
    else:
        if power is None and a.get('voltage_v') is not None and a.get('current_a') is not None:
            power = a['voltage_v'] * a['current_a']; approximate = True
        tier, band = ('B', .30) if power is not None else ('C', .50)
        if power is None: power = default['watts']
        basis = ('Approximate volts × amps; power factor is unknown' if approximate else
                 'Confirmed rated input watts' if tier == 'B' else 'Category default watts; placeholder estimate')
        energy = power * hours * 30 * factor * quantity / 1000
        assumptions = {'watts':power, 'hours_per_day':hours, 'days':30, 'load_factor':factor,
                       'quantity':quantity, 'range_percent':int(band*100)}
    if energy < 0 or not math.isfinite(energy): raise ValueError('Invalid energy result.')
    return {'id':a.get('id'), 'name':a.get('name',category), 'category':category, 'tier':tier,
            'placeholder':tier=='C', 'approximate_power':approximate, 'basis':basis,
            'monthly_kwh':energy, 'low_kwh':energy*(1-band), 'high_kwh':energy*(1+band),
            'assumptions':assumptions}

def reconcile(estimated, billed=None, amount=None):
    usable = billed is not None and billed > 0
    coverage = estimated / billed if usable else None
    band = ('good_match' if .8 <= coverage <= 1.2 else 'under_explained' if coverage < .8 else 'over_estimated') if usable else 'unavailable'
    return {'estimated_total':estimated, 'billed_kwh':billed,
            'gap_kwh':billed-estimated if billed is not None else None,
            'coverage':coverage, 'coverage_percent':coverage*100 if usable else None,
            'band':band, 'avg_rate':amount/billed if usable and amount is not None else None,
            'total_amount':amount}

def audit(appliances: list[dict], bill: dict | None = None) -> dict:
    rows = sorted([estimate_appliance(a) for a in appliances], key=lambda a:a['monthly_kwh'], reverse=True)
    total = sum(a['monthly_kwh'] for a in rows)
    bill = bill or {}
    result = reconcile(total, bill.get('units_kwh'), bill.get('total_amount'))
    for a in rows:
        a['share_percent'] = a['monthly_kwh']/total*100 if total > 0 else 0
        a['estimated_cost'] = a['monthly_kwh']*result['avg_rate'] if result['avg_rate'] is not None else None
    return {**result, 'appliances':rows, 'period':'Standardized month', 'days':30,
            'range_low':sum(a['low_kwh'] for a in rows), 'range_high':sum(a['high_kwh'] for a in rows),
            'placeholder_count':sum(a['placeholder'] for a in rows),
            'caveats':['All appliance figures are estimates from labels, usage, and editable defaults.',
                       'Range bands are assumptions, not statistical confidence intervals.',
                       'The estimate uses annual kWh divided by twelve or a standardized thirty day month.',
                       'Coverage is a model comparison, not measured device attribution.',
                       'Average bill rate includes payable charges; slab pricing means true marginal cost may be higher.']}

def display_output(value):
    if isinstance(value, dict): return {k:display_output(v) for k,v in value.items()}
    if isinstance(value, list): return [display_output(v) for v in value]
    if isinstance(value, float): return displayed(value)
    return value
