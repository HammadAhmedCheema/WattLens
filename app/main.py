from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db import init_db
from .config import settings
from fastapi import Request, Depends
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from .models import Appliance
from .db import get_session
from .web import render, is_demo
from .routes import appliances, dashboard, bills, analysis
from fastapi.responses import RedirectResponse
from .demo import seed_demo
from .web import payload

@asynccontextmanager
async def lifespan(app):
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    if settings.demo_mode:
        from .db import engine
        with Session(engine) as session: seed_demo(session)
    yield

app = FastAPI(title='WattLens', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(__import__('pathlib').Path(__file__).parent / 'static')), name='static')
settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=str(settings.upload_dir)), name='uploads')
app.include_router(appliances.router)
app.include_router(dashboard.router)
app.include_router(bills.router)
app.include_router(analysis.router)

@app.get('/')
async def index(request: Request, session: Session = Depends(get_session)):
    if is_demo(request): seed_demo(session)
    records = session.exec(select(Appliance).where(Appliance.is_demo == is_demo(request))).all()
    return render(request, 'index.html', appliances=records, active='home')

@app.post('/mode')
async def mode(request: Request, session: Session=Depends(get_session)):
    data=await payload(request)
    choice='demo' if data.get('mode')=='demo' else 'live'
    if choice=='demo': seed_demo(session)
    response=RedirectResponse('/dashboard' if choice=='demo' else '/',status_code=303)
    response.set_cookie('wattlens_mode',choice,httponly=True,samesite='strict')
    return response

@app.get('/healthz')
async def healthz():
    # A configuration check, not a paid generation request or a claim of connectivity.
    from fastapi.responses import JSONResponse
    configured = bool(settings.api_key)
    return JSONResponse({'ok': configured, 'provider': 'openrouter',
        'model': settings.model_name, 'key_configured': configured,
        'connectivity_tested': False, 'demo_mode': settings.demo_mode},
        status_code=200 if configured else 503)
