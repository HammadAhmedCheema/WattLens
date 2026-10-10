from typing import Literal
from pydantic import BaseModel, Field, FiniteFloat, ConfigDict, field_validator

Category = Literal['refrigerator', 'air_conditioner', 'fan', 'light', 'tv', 'washing_machine',
                   'water_heater', 'iron', 'microwave', 'pump', 'other']
LabelType = Literal['energyguide_us', 'eu_a_to_g', 'star_rating', 'nameplate_only', 'other']
Status = Literal['read', 'unclear', 'absent']
LABEL_FIELDS = ['annual_kwh', 'rated_power_w', 'voltage_v', 'current_a', 'category']
BILL_FIELDS = ['units_kwh', 'total_amount', 'billing_month']

class Transcription(BaseModel):
    visible_text: list[str] = Field(default_factory=list)

class ApplianceExtraction(BaseModel):
    model_config = ConfigDict(extra='ignore')
    category: Category | None = None
    brand: str | None = None
    model: str | None = None
    label_type: LabelType | None = None
    annual_kwh: FiniteFloat | None = None
    rated_power_w: FiniteFloat | None = None
    voltage_v: FiniteFloat | None = None
    current_a: FiniteFloat | None = None
    rating: str | None = None
    capacity: str | None = None
    visible_text: list[str] = Field(default_factory=list)
    field_status: dict[str, Status] = Field(default_factory=dict)

class BillExtraction(BaseModel):
    billing_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    units_kwh: FiniteFloat | None = None
    total_amount: FiniteFloat | None = None
    tariff_text: str | None = None
    previous_month_units: FiniteFloat | None = None
    visible_text: list[str] = Field(default_factory=list)
    field_status: dict[str, Status] = Field(default_factory=dict)

class ApplianceInput(ApplianceExtraction):
    name: str = Field(min_length=1, max_length=100)
    category: Category = 'other'
    quantity: int = Field(default=1, ge=1, le=1000)
    hours_per_day: FiniteFloat = Field(default=4, ge=0, le=24)
    load_factor: FiniteFloat = Field(default=1, ge=0, le=1)
    source_image: str | None = None
    confirmed: Literal[True] = True
    @field_validator('annual_kwh', 'rated_power_w', 'voltage_v', 'current_a')
    @classmethod
    def nonnegative(cls, v):
        if v is not None and v < 0:
            raise ValueError('Confirmed values cannot be negative.')
        return v

class BillInput(BillExtraction):
    source_image: str | None = None
    confirmed: Literal[True] = True
    @field_validator('units_kwh', 'total_amount', 'previous_month_units')
    @classmethod
    def nonnegative(cls, v):
        if v is not None and v < 0:
            raise ValueError('Confirmed values cannot be negative.')
        return v

class BriefOutput(BaseModel):
    headline: str = Field(max_length=250)
    findings: list[str] = Field(min_length=3, max_length=3)
    actions: list[str] = Field(min_length=3, max_length=3)
    caveats: list[str] = Field(default_factory=list)
