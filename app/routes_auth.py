from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user, verify_password
from app.database import get_db
from app.services import log_event

templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == models.ROLE_ADMIN:
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return RedirectResponse(url="/auditor/dashboard", status_code=303)


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        if user.role == models.ROLE_ADMIN:
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        return RedirectResponse(url="/auditor/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": request.query_params.get("error")},
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/login?error=Invalid email or password", status_code=303)

    request.session["user_id"] = user.id
    request.session["role"] = user.role

    log_event(db=db, event_type="LOGIN", request=request, user=user, commit=True)

    if user.role == models.ROLE_ADMIN:
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return RedirectResponse(url="/auditor/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
