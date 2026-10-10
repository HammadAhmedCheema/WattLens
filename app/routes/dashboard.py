from fastapi import APIRouter, Request, Depends
from sqlmodel import Session, select
from ..models import Appliance, Bill
from ..db import get_session
from ..engine import audit, display_output
from ..web import render, is_demo

router = APIRouter()

def household_data(session, demo):
    appliances = session.exec(select(Appliance).where(Appliance.is_demo==demo).order_by(Appliance.id)).all()
    bill = session.exec(select(Bill).where(Bill.is_demo==demo).order_by(Bill.id.desc())).first()
    return appliances, bill

@router.get('/dashboard')
async def dashboard(request: Request, session: Session = Depends(get_session)):
    appliances,bill = household_data(session,is_demo(request))
    output = display_output(audit([a.model_dump() for a in appliances],bill.model_dump() if bill else None))
    if 'application/json' in request.headers.get('accept',''): return output
    return render(request,'dashboard.html', output=output, records=appliances, bill=bill, active='dashboard')
