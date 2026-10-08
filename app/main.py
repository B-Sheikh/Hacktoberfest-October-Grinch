"""Waterline composition root; feature code lives in four domain packages."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import db, settings
from .common import STATIC
from .office import auth
from .office.routes import router as office_router
from .citizen.routes import router as citizen_router
from .intelligence.routes import router as intelligence_router
from .operations.routes import router as operations_router

@asynccontextmanager
async def lifespan(app):
    db.init()
    settings.UPLOADS.mkdir(parents=True,exist_ok=True)
    yield

app = FastAPI(title="Waterline", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.middleware('http')
async def admin_boundary(request:Request, call_next):
    path=request.url.path
    public_api=path in ['/api/config','/api/health','/api/reports','/api/auth/login'] or path.startswith('/api/public/') or path.startswith('/api/report-link/')
    protected_api=path.startswith('/api/') and not public_api
    protected_page=path in ['/office','/authority','/command','/responders','/docs','/redoc','/openapi.json'] or path.startswith('/field/') or (path.startswith('/static/') and path.endswith('/index.html'))
    if protected_api or protected_page:
        request.state.admin=auth.session(request)
        if not request.state.admin:
            if protected_page: return RedirectResponse('/admin/login',status_code=303,headers={'Cache-Control':'no-store'})
            return JSONResponse({'detail':'Admin login required'},status_code=401,headers={'Cache-Control':'no-store'})
        if request.method not in ['GET','HEAD','OPTIONS'] and (request.headers.get('x-waterline-request')!='1' or not auth.same_origin(request)):
            return JSONResponse({'detail':'Invalid request origin'},status_code=403)
    response=await call_next(request)
    if protected_api or protected_page or path.startswith('/api/auth') or path=='/admin/login':
        response.headers.setdefault('Cache-Control','no-store')
    # OSM tiles require a Referer. Send only our origin, keeping report tokens private.
    response.headers['Referrer-Policy']='strict-origin'
    return response

for router in (office_router, citizen_router, intelligence_router, operations_router):
    app.include_router(router)
