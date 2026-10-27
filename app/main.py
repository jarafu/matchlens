from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.config import Settings
from app.db import connect
from app.web.auth import router as auth_router, authenticated


def create_app(settings=None):
    settings=settings or Settings()
    if settings.secure_cookies and settings.database_url.startswith('sqlite'):
        raise ValueError('Hosted mode requires persistent PostgreSQL')
    app=FastAPI(title='MatchLens',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.settings=settings;app.state.db=connect(settings.database_url)
    root=Path(__file__).parent
    app.state.templates=Jinja2Templates(directory=root/'templates')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.allowed_hosts)
    app.mount('/static',StaticFiles(directory=root/'static'),name='static')
    app.include_router(auth_router)

    @app.middleware('http')
    async def security_headers(request,call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.get('/healthz')
    def health(): return {'status':'ok'}

    @app.get('/')
    def index(request: Request):
        try: csrf=authenticated(request)
        except Exception: return RedirectResponse('/login',303)
        return app.state.templates.TemplateResponse(request,'dashboard.html',{'csrf':csrf,'timezone':settings.timezone})

    from app.web.routes import router
    app.include_router(router,dependencies=[Depends(authenticated)])
    return app

app=create_app()
