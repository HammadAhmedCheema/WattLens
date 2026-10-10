from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field

def now():
    return datetime.now(timezone.utc)

class Household(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = 'My household'

class Appliance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(default=1, foreign_key='household.id')
    name: str
    category: str = 'other'
    brand: Optional[str] = None
    model: Optional[str] = None
    label_type: str = 'other'
    annual_kwh: Optional[float] = None
    rated_power_w: Optional[float] = None
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    rating: Optional[str] = None
    capacity: Optional[str] = None
    quantity: int = 1
    hours_per_day: float = 4
    load_factor: float = 1
    field_status_json: str = '{}'
    visible_text_json: str = '[]'
    source_image: Optional[str] = None
    confirmed: bool = True
    is_demo: bool = False
    created_at: datetime = Field(default_factory=now)

class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(default=1, foreign_key='household.id')
    billing_month: Optional[str] = None
    units_kwh: Optional[float] = None
    total_amount: Optional[float] = None
    tariff_text: Optional[str] = None
    previous_month_units: Optional[float] = None
    field_status_json: str = '{}'
    source_image: Optional[str] = None
    confirmed: bool = True
    is_demo: bool = False
    created_at: datetime = Field(default_factory=now)

class Analysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(default=1, foreign_key='household.id')
    bill_id: Optional[int] = Field(default=None, foreign_key='bill.id')
    appliance_snapshot_json: str
    numbers_json: str
    brief_json: str
    model_name: str
    mode: str = 'live'
    brief_source: str
    created_at: datetime = Field(default_factory=now)
