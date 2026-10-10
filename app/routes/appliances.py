import json
from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import Appliance
from ..schemas import ApplianceInput, ApplianceExtraction
from ..extraction import preprocess, extract, UploadError, MAX_BYTES, sanity_flags
from ..defaults import DEFAULTS
from ..web import render, payload, validate, validate_source, is_demo

router = APIRouter()

async def extract_upload(file, kind, demo):
    data = await file.read(MAX_BYTES + 1)
    try: source, clean = preprocess(data, file.filename or '')
    except UploadError as e: raise HTTPException(e.status_code, str(e))
    result = await extract(clean, kind, demo)
    result.update(source_image=source, kind=kind)
    return result

@router.post('/appliances/extract')
async def photo(request: Request, files: list[UploadFile] = File()):
    if not files or len(files) > 12:
        raise HTTPException(400, 'Choose between one and twelve appliance photos.')
    results = []
    for file in files:
        results.append(await extract_upload(file, 'appliance', is_demo(request)))
    if 'application/json' in request.headers.get('accept',''):
        return {'drafts': results}
    return render(request, 'review.html', drafts=results, editing=False)

@router.get('/appliances/manual')
async def manual_form(request: Request):
    return render(request, 'review.html', drafts=[{'fields':ApplianceExtraction(category='fan').model_dump(),
        'flags':{}, 'source_image':None, 'kind':'appliance','provenance':'manual_entry'}], editing=False)

@router.get('/appliances/{appliance_id}/edit')
async def edit_form(appliance_id: int, request: Request, session: Session = Depends(get_session)):
    a = session.get(Appliance, appliance_id)
    if not a or a.is_demo != is_demo(request): raise HTTPException(404, 'Appliance not found.')
    fields = a.model_dump()
    fields['field_status'] = json.loads(a.field_status_json)
    fields['visible_text'] = json.loads(a.visible_text_json)
    return render(request, 'review.html', drafts=[{'fields':fields,'flags':sanity_flags(fields,'appliance'),
        'source_image':a.source_image,'kind':'appliance','provenance':'confirmed_record','id':a.id}], editing=True)

async def save_record(request, session, appliance=None):
    data = await payload(request)
    category = data.get('category') or 'other'
    default = DEFAULTS.get(category, DEFAULTS['other'])
    for field,key in [('hours_per_day','hours'),('load_factor','load_factor')]:
        if data.get(field) is None: data[field] = default[key]
    item = validate(ApplianceInput, data)
    validate_source(item.source_image)
    values = item.model_dump(exclude={'field_status','visible_text'})
    values.update(label_type=item.label_type or 'other', field_status_json=json.dumps(item.field_status),
                  visible_text_json=json.dumps(item.visible_text), is_demo=is_demo(request))
    if appliance:
        for key,value in values.items(): setattr(appliance,key,value)
    else: appliance = Appliance(**values)
    session.add(appliance); session.commit(); session.refresh(appliance)
    if request.headers.get('content-type','').startswith('application/json'):
        return appliance.model_dump()
    if request.headers.get('HX-Request'):
        return render(request,'saved.html', name=appliance.name)
    return RedirectResponse('/dashboard',status_code=303)

@router.post('/appliances')
@router.post('/appliances/manual')
async def save(request: Request, session: Session = Depends(get_session)):
    return await save_record(request, session)

@router.put('/appliances/{appliance_id}')
async def update(appliance_id: int, request: Request, session: Session = Depends(get_session)):
    a = session.get(Appliance, appliance_id)
    if not a or a.is_demo != is_demo(request): raise HTTPException(404,'Appliance not found.')
    return await save_record(request,session,a)

@router.delete('/appliances/{appliance_id}')
async def remove(appliance_id: int, request: Request, session: Session = Depends(get_session)):
    a = session.get(Appliance,appliance_id)
    if not a or a.is_demo != is_demo(request): raise HTTPException(404,'Appliance not found.')
    session.delete(a); session.commit()
    if request.headers.get('HX-Request'): return render(request,'deleted.html')
    return {'deleted':appliance_id}
