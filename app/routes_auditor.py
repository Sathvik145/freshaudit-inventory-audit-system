from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user, is_auditor
from app.database import get_db
from app.services import (
    auditor_has_access,
    get_assigned_warehouses,
    get_count_map,
    get_tasks_for_auditor,
    submit_count,
)

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/auditor", tags=["auditor"])


def require_auditor_or_redirect(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None, RedirectResponse(url="/login", status_code=303)
    if not is_auditor(user):
        return None, RedirectResponse(url="/admin/dashboard", status_code=303)
    return user, None


@router.get("/dashboard")
def auditor_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_auditor_or_redirect(request, db)
    if redirect:
        return redirect

    warehouses = get_assigned_warehouses(db, user.id)
    tasks = get_tasks_for_auditor(db, user.id)

    return templates.TemplateResponse(
        request,
        "auditor_dashboard.html",
        {
            "request": request,
            "user": user,
            "warehouses": warehouses,
            "tasks": tasks,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


@router.get("/tasks/{task_id}/count")
def count_screen(request: Request, task_id: int, db: Session = Depends(get_db)):
    user, redirect = require_auditor_or_redirect(request, db)
    if redirect:
        return redirect

    task = db.query(models.AuditTask).filter(models.AuditTask.id == task_id).first()
    if not task:
        return RedirectResponse(url="/auditor/dashboard?error=Audit task not found", status_code=303)

    if not auditor_has_access(db, user.id, task.warehouse_id):
        return RedirectResponse(url="/auditor/dashboard?error=Access denied for this warehouse", status_code=303)

    snapshot_lines = (
        db.query(models.AuditSnapshotLine)
        .filter(models.AuditSnapshotLine.audit_task_id == task_id)
        .order_by(models.AuditSnapshotLine.shelf_location, models.AuditSnapshotLine.item_sku)
        .all()
    )
    count_map = get_count_map(db, task_id)

    # Important BRD point: do not send snapshot_quantity to the auditor UI.
    count_rows = []
    for line in snapshot_lines:
        count = count_map.get((line.item_sku, line.shelf_location))
        count_rows.append(
            {
                "item_sku": line.item_sku,
                "item_name": line.item_name,
                "shelf_location": line.shelf_location,
                "is_submitted": count is not None,
                "audited_quantity": count.audited_quantity if count else None,
            }
        )

    return templates.TemplateResponse(
        request,
        "count_screen.html",
        {
            "request": request,
            "user": user,
            "task": task,
            "count_rows": count_rows,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/tasks/{task_id}/submit-count")
def submit_count_route(
    request: Request,
    task_id: int,
    shelf_location: str = Form(...),
    item_sku: str = Form(...),
    location_scan: str = Form(...),
    sku_scan: str = Form(...),
    audited_quantity: int = Form(...),
    db: Session = Depends(get_db),
):
    user, redirect = require_auditor_or_redirect(request, db)
    if redirect:
        return redirect

    success, message = submit_count(
        db=db,
        auditor=user,
        task_id=task_id,
        shelf_location=shelf_location,
        item_sku=item_sku,
        location_scan=location_scan,
        sku_scan=sku_scan,
        audited_quantity=audited_quantity,
        request=request,
    )

    if success:
        return RedirectResponse(
            url=f"/auditor/tasks/{task_id}/count?success={quote_plus(message)}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/auditor/tasks/{task_id}/count?error={quote_plus(message)}",
        status_code=303,
    )
