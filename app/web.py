import json
import re
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from .config import ROOT, settings
from .defaults import DEFAULTS

templates = Jinja2Templates(directory=str(ROOT / 'app' / 'templates'))
templates.env.globals.update(model_name=settings.model_name, defaults=DEFAULTS)

def is_demo(request):
    return request.cookies.get('wattlens_mode', 'demo' if settings.demo_mode else 'live') == 'demo'

def render(request, name, **context):
    context.update(demo=is_demo(request), request=request)
    return templates.TemplateResponse(request=request, name=name, context=context)

async def payload(request):
    if request.headers.get('content-type', '').startswith('application/json'):
        return await request.json()
    data = dict(await request.form())
    for k,v in list(data.items()):
        if v == '': data[k] = None
    for k in ['field_status', 'visible_text']:
        if isinstance(data.get(k), str):
            try: data[k] = json.loads(data[k])
            except ValueError: raise HTTPException(422, f'Invalid {k}.')
    return data

def validate_source(source):
    if source is None: return None
    if not re.fullmatch(r'[a-f0-9]{32}\.jpg', source) or not (settings.upload_dir / source).is_file():
        raise HTTPException(422, 'Invalid source image. Upload the photo again.')
    return source

def validate(schema, data):
    try: return schema.model_validate(data)
    except ValidationError as e:
        raise HTTPException(422, '; '.join(f'{".".join(map(str,x["loc"]))}: {x["msg"]}' for x in e.errors()))
