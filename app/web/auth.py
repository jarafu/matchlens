import hashlib
import secrets
import os
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete, func
from app.domain import now, stamp, parse_time
from app.models import LoginSession, LoginAttempt
from dotenv import set_key

router = APIRouter()
hasher = PasswordHasher()


def hash_password(password): return hasher.hash(password)
def digest(token): return hashlib.sha256(token.encode()).hexdigest()


def require_local(request):
    if request.app.state.settings.secure_cookies or not request.client or request.client.host not in {'127.0.0.1','::1'}:
        raise HTTPException(403,'Use local setup on this computer; hosted secrets belong in your hosting settings')


def save_secret(settings,key,value):
    path=settings.secrets_file
    fd=os.open(path,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
    os.chmod(path,0o600)
    set_key(str(path),key,value)
    os.chmod(path,0o600)


@router.post('/setup')
def setup(request: Request,password: str=Form(...),confirm: str=Form(...),csrf: str=Form(...),football_token: str=Form('')):
    require_local(request);settings=request.app.state.settings
    if settings.password_hash: raise HTTPException(403,'Owner setup has already been completed')
    if not csrf or not secrets.compare_digest(csrf,request.cookies.get('login_csrf','')): raise HTTPException(403,'Reload the setup form')
    if len(password)<12 or len(password)>256 or password!=confirm: raise HTTPException(422,'Use matching passwords of 12–256 characters')
    token=football_token.strip()
    if token and (not token.isascii() or not token.replace('-','').replace('_','').isalnum() or not 8<=len(token)<=200): raise HTTPException(422,'API key contains unsupported characters')
    settings.password_hash=hash_password(password)
    save_secret(settings,'OWNER_PASSWORD_HASH',settings.password_hash)
    if token: save_secret(settings,'FOOTBALL_DATA_TOKEN',token);settings.football_token=token
    return login(request,password,csrf)


def authenticated(request: Request):
    token=request.cookies.get('session','')
    with request.app.state.db() as db:
        sess=db.get(LoginSession,digest(token)) if token else None
        if not sess or parse_time(sess.expires_at)<=now(): raise HTTPException(401,"Sign in to continue")
        if request.method not in {'GET','HEAD','OPTIONS'}:
            csrf=request.headers.get('X-CSRF-Token','')
            if not secrets.compare_digest(csrf,sess.csrf): raise HTTPException(403,"Refresh the page and try again")
        return sess.csrf


@router.get('/login')
def login_page(request: Request):
    csrf=secrets.token_urlsafe(32)
    response=request.app.state.templates.TemplateResponse(request, 'login.html', {'csrf':csrf,'error':None,'configured':bool(request.app.state.settings.password_hash)})
    response.set_cookie('login_csrf',csrf,httponly=True,secure=request.app.state.settings.secure_cookies,samesite='strict',max_age=600)
    return response


@router.post('/login')
def login(request: Request,password: str=Form(...),csrf: str=Form(...)):
    settings=request.app.state.settings
    if not csrf or not secrets.compare_digest(csrf,request.cookies.get('login_csrf','')): raise HTTPException(403,'Invalid form session. Reload the login page.')
    if not settings.password_hash: raise HTTPException(503,'Owner password has not been configured. Run local setup.')
    ip=request.client.host if request.client else 'unknown'
    with request.app.state.db() as db:
        cutoff=(now()-timedelta(minutes=15)).isoformat()
        db.execute(delete(LoginAttempt).where(LoginAttempt.at<cutoff))
        count=db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip==ip))
        if count>=5: raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
        try: valid=hasher.verify(settings.password_hash,password)
        except (VerificationError,InvalidHashError): valid=False
        if not valid:
            db.add(LoginAttempt(ip=ip,at=stamp()));db.commit()
            return request.app.state.templates.TemplateResponse(request,'login.html',{'csrf':csrf,'error':'Password not recognised.','configured':True},status_code=401)
        old=request.cookies.get('session')
        if old: db.execute(delete(LoginSession).where(LoginSession.id==digest(old)))
        token=secrets.token_urlsafe(48)
        db.add(LoginSession(id=digest(token),csrf=secrets.token_urlsafe(32),expires_at=(now()+timedelta(hours=12)).isoformat()))
        db.execute(delete(LoginAttempt).where(LoginAttempt.ip==ip));db.commit()
    response=RedirectResponse('/',status_code=303)
    response.set_cookie('session',token,httponly=True,secure=settings.secure_cookies,samesite='strict',max_age=43200)
    response.delete_cookie('login_csrf')
    return response


@router.post('/logout')
def logout(request: Request):
    authenticated(request)
    with request.app.state.db() as db:
        db.execute(delete(LoginSession).where(LoginSession.id==digest(request.cookies.get('session',''))));db.commit()
    response=RedirectResponse('/login',status_code=303);response.delete_cookie('session');return response
