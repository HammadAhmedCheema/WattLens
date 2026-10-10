import pytest
from pydantic import ValidationError
from app.schemas import ApplianceExtraction, ApplianceInput, BillExtraction
from app.extraction import sanity_flags

def test_schema_and_nulls():
    assert ApplianceExtraction().rated_power_w is None
    with pytest.raises(ValidationError): ApplianceExtraction(category='spaceship')
    with pytest.raises(ValidationError): BillExtraction(billing_month='2026-99')
    with pytest.raises(ValidationError): ApplianceExtraction(rated_power_w=float('nan'))
    with pytest.raises(ValidationError): ApplianceInput(name='fan', hours_per_day=25)
    with pytest.raises(ValidationError): ApplianceInput(name='fan', quantity=0)

def test_flags_do_not_correct_values():
    data={'rated_power_w': 7000, 'annual_kwh': 2}
    assert set(sanity_flags(data,'appliance')) == set(data)
    assert data['rated_power_w'] == 7000
    assert 'total_amount' in sanity_flags({'units_kwh':10,'total_amount':99999},'bill')
    assert 'units_kwh' in sanity_flags({'units_kwh':0},'bill')
