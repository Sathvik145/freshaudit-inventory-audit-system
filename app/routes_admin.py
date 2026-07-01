import csv
import io
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user, is_admin
from app.database import get_db
from app.services import create_audit_task, get_variance_report_rows, log_event

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_or_redirect(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None, RedirectResponse(url="/login", status_code=303)
    if not is_admin(user):
        return None, RedirectResponse(url="/auditor/dashboard", status_code=303)
    return user, None


@router.get("/dashboard")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_admin_or_redirect(request, db)
    if redirect:
        return redirect

    tasks = db.query(models.AuditTask).order_by(models.AuditTask.created_at.desc()).all()
    warehouses = db.query(models.Warehouse).order_by(models.Warehouse.warehouse_code).all()
    auditors = (
        db.query(models.User)
        .filter(models.User.role == models.ROLE_AUDITOR)
        .order_by(models.User.name)
        .all()
    )
    inventory_rows = db.query(models.Inventory).order_by(models.Inventory.shelf_location).limit(20).all()
    event_logs = (
        db.query(models.AuditEventLog)
        .order_by(models.AuditEventLog.created_at.desc())
        .limit(15)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "request": request,
            "user": user,
            "tasks": tasks,
            "warehouses": warehouses,
            "auditors": auditors,
            "inventory_rows": inventory_rows,
            "event_logs": event_logs,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


@router.get("/create-audit")
def create_audit_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_admin_or_redirect(request, db)
    if redirect:
        return redirect

    warehouses = db.query(models.Warehouse).order_by(models.Warehouse.warehouse_code).all()
    return templates.TemplateResponse(
        request,
        "create_audit.html",
        {
            "request": request,
            "user": user,
            "warehouses": warehouses,
            "error": request.query_params.get("error"),
        },
    )


@router.post("/create-audit")
def create_audit_submit(
    request: Request,
    warehouse_id: int = Form(...),
    target_type: str = Form(...),
    target_value: str = Form(...),
    db: Session = Depends(get_db),
):
    user, redirect = require_admin_or_redirect(request, db)
    if redirect:
        return redirect

    task, error = create_audit_task(
        db=db,
        admin=user,
        warehouse_id=warehouse_id,
        target_type=target_type,
        target_value=target_value,
        request=request,
    )
    if error:
        return RedirectResponse(url=f"/admin/create-audit?error={quote_plus(error)}", status_code=303)

    msg = quote_plus(f"Audit task {task.audit_task_id} created with frozen snapshot")
    return RedirectResponse(url=f"/admin/dashboard?success={msg}", status_code=303)


@router.post("/map-auditor")
def map_auditor_to_warehouse(
    request: Request,
    auditor_id: int = Form(...),
    warehouse_id: int = Form(...),
    db: Session = Depends(get_db),
):
    user, redirect = require_admin_or_redirect(request, db)
    if redirect:
        return redirect

    auditor = (
        db.query(models.User)
        .filter(models.User.id == auditor_id, models.User.role == models.ROLE_AUDITOR)
        .first()
    )
    warehouse = db.query(models.Warehouse).filter(models.Warehouse.id == warehouse_id).first()

    if not auditor:
        return RedirectResponse(url="/admin/dashboard?error=Auditor not found", status_code=303)
    if not warehouse:
        return RedirectResponse(url="/admin/dashboard?error=Warehouse not found", status_code=303)

    existing_mapping = (
        db.query(models.AuditorWarehouseMapping)
        .filter(
            models.AuditorWarehouseMapping.auditor_id == auditor_id,
            models.AuditorWarehouseMapping.warehouse_id == warehouse_id,
        )
        .first()
    )

    if existing_mapping:
        existing_mapping.is_active = True
    else:
        db.add(
            models.AuditorWarehouseMapping(
                auditor_id=auditor_id,
                warehouse_id=warehouse_id,
                is_active=True,
            )
        )

    log_event(
        db=db,
        event_type="AUDITOR_MAPPED_TO_WAREHOUSE",
        request=request,
        user=user,
        warehouse_id=warehouse_id,
        commit=False,
    )
    db.commit()

    msg = quote_plus(f"{auditor.name} mapped to {warehouse.warehouse_code}")
    return RedirectResponse(url=f"/admin/dashboard?success={msg}", status_code=303)


@router.get("/audit-tasks/{task_id}/variance")
def variance_report_page(request: Request, task_id: int, db: Session = Depends(get_db)):
    user, redirect = require_admin_or_redirect(request, db)
    if redirect:
        return redirect

    task = db.query(models.AuditTask).filter(models.AuditTask.id == task_id).first()
    if not task:
        return RedirectResponse(url="/admin/dashboard?error=Audit task not found", status_code=303)

    rows = get_variance_report_rows(db, task_id)
    return templates.TemplateResponse(
        request,
        "variance_report.html",
        {
            "request": request,
            "user": user,
            "task": task,
            "rows": rows,
        },
    )


@router.get("/audit-tasks/{task_id}/variance/download")
def variance_report_download(request: Request, task_id: int, db: Session = Depends(get_db)):
    user, redirect = require_admin_or_redirect(request, db)
    if redirect:
        return redirect

    task = db.query(models.AuditTask).filter(models.AuditTask.id == task_id).first()
    if not task:
        return RedirectResponse(url="/admin/dashboard?error=Audit task not found", status_code=303)

    rows = get_variance_report_rows(db, task_id)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "Audit_Task_ID",
            "Warehouse_ID",
            "Item_SKU",
            "Item_Name",
            "Shelf_Location",
            "Snapshot_Quantity",
            "Audited_Quantity",
            "Variance",
            "Shrinkage_Rate",
            "Count_Status",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: ("" if value is None else value) for key, value in row.items()})

    output.seek(0)

    log_event(
        db=db,
        event_type="REPORT_DOWNLOADED",
        request=request,
        user=user,
        audit_task_id=task.id,
        warehouse_id=task.warehouse_id,
        commit=True,
    )

    filename = f"variance_report_{task.audit_task_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
