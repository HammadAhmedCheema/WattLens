import json
from fastapi import APIRouter, Request, Depends, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import Bill
from ..schemas import BillInput, BillExtraction
from ..web import render, is_demo, payload, validate, validate_source
from .appliances import extract_upload

router = APIRouter()

@router.get('/bills')
async def bills(request: Request, session: Session = Depends(get_session)):
    records=session.exec(select(Bill).where(Bill.is_demo==is_demo(request)).order_by(Bill.id.desc())).all()
    if 'application/json' in request.headers.get('accept',''): return [b.model_dump() for b in records]
    return render(request,'bills.html',bills=records,active='bills')

@router.get('/bills/manual')
async def manual(request: Request):
    return render(request,'bill_review.html',draft={'fields':BillExtraction().model_dump(),'flags':{},'source_image':None,'provenance':'manual_entry'},active='bills')

@router.post('/bills/extract')
async def photo(request: Request, file: UploadFile = File()):
    result=await extract_upload(file,'bill',is_demo(request))
    if 'application/json' in request.headers.get('accept',''): return result
    return render(request,'bill_review.html',draft=result,active='bills')

@router.post('/bills')
async def save(request: Request, session: Session = Depends(get_session)):
    item=validate(BillInput,await payload(request));validate_source(item.source_image)
    data=item.model_dump(exclude={'visible_text','field_status'})
    bill=Bill(**data,field_status_json=json.dumps(item.field_status),is_demo=is_demo(request))
    session.add(bill);session.commit();session.refresh(bill)
    if request.headers.get('content-type','').startswith('application/json'): return bill.model_dump()
    return RedirectResponse('/analysis',status_code=303)
