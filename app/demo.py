import json
from sqlmodel import select
from .config import ROOT
from .models import Appliance, Bill

def seed_demo(session):
    if session.exec(select(Appliance).where(Appliance.is_demo==True)).first(): return
    data=json.loads((ROOT/'demo'/'household.json').read_text())
    for item in data['appliances']: session.add(Appliance(**item,is_demo=True))
    if not session.exec(select(Bill).where(Bill.is_demo==True)).first():
        session.add(Bill(**data['bill'],is_demo=True))
    session.commit()
