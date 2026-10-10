import json
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Bill, Analysis
from ..engine import audit, display_output
from ..config import settings
from ..web import render, is_demo, payload
from ..brief import generate
from .dashboard import household_data

router=APIRouter()

def get_data(request, session, bill_id=None):
    appliances,bill=household_data(session,is_demo(request))
    if bill_id is not None:
        bill=session.get(Bill,bill_id)
        if not bill or bill.is_demo!=is_demo(request): raise HTTPException(404,'Bill not found.')
    output=display_output(audit([a.model_dump() for a in appliances],bill.model_dump() if bill else None))
    return appliances,bill,output

@router.get('/analysis')
async def comparison(request: Request,bill_id: int | None=None, session: Session=Depends(get_session)):
    appliances,bill,output=get_data(request,session,bill_id)
    latest=session.exec(select(Analysis).where(Analysis.mode==('demo' if is_demo(request) else 'live')).order_by(Analysis.id.desc())).first()
    return render(request,'analysis.html',output=output,bill=bill,brief=None,brief_source=None,error=None,latest=latest,active='analysis')

@router.post('/analysis')
async def analyse(request: Request,session: Session=Depends(get_session)):
    body=await payload(request)
    try: bill_id=int(body['bill_id']) if body.get('bill_id') else None
    except (ValueError,TypeError): raise HTTPException(422,'Invalid bill ID.')
    appliances,bill,output=get_data(request,session,bill_id)
    if not appliances: raise HTTPException(422,'Confirm at least one appliance before generating a brief.')
    brief,source,error=await generate(output,is_demo(request))
    record=Analysis(bill_id=bill.id if bill else None,
        appliance_snapshot_json=json.dumps([a.model_dump(mode='json') for a in appliances]),
        numbers_json=json.dumps(output),brief_json=json.dumps(brief),model_name=settings.model_name,
        mode='demo' if is_demo(request) else 'live',brief_source=source)
    session.add(record);session.commit();session.refresh(record)
    if 'application/json' in request.headers.get('accept',''):
        return {'id':record.id,'numbers':output,'brief':brief,'brief_source':source,'error':error}
    if request.headers.get('HX-Request'):
        return render(request,'brief_fragment.html',brief=brief,brief_source=source,error=error,analysis_id=record.id)
    return render(request,'analysis.html',output=output,bill=bill,brief=brief,brief_source=source,error=error,latest=record,active='analysis')

@router.get('/analysis/{analysis_id}')
async def saved(analysis_id: int,request: Request,session: Session=Depends(get_session)):
    record=session.get(Analysis,analysis_id)
    if not record or record.mode!=('demo' if is_demo(request) else 'live'): raise HTTPException(404,'Analysis not found.')
    output=json.loads(record.numbers_json)
    bill=session.get(Bill,record.bill_id) if record.bill_id else None
    return render(request,'analysis.html',output=output,bill=bill,brief=json.loads(record.brief_json),
        brief_source=record.brief_source,error=None,latest=record,active='analysis',snapshot=True)
