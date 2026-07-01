import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import Request
from sqlalchemy.orm import Session

from app import models
from app.auth import client_ip, device_info


def generate_audit_task_code() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = random.randint(1000, 9999)
    return f"AUD-{timestamp}-{suffix}"


def log_event(
    db: Session,
    event_type: str,
    request: Optional[Request] = None,
    user: Optional[models.User] = None,
    audit_task_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    item_sku: Optional[str] = None,
    shelf_location: Optional[str] = None,
    commit: bool = True,
) -> None:
    event = models.AuditEventLog(
        audit_task_id=audit_task_id,
        user_id=user.id if user else None,
        event_type=event_type,
        warehouse_id=warehouse_id,
        item_sku=item_sku,
        shelf_location=shelf_location,
        ip_address=client_ip(request) if request else "unknown",
        device_info=device_info(request) if request else "unknown",
    )
    db.add(event)
    if commit:
        db.commit()


def create_audit_task(
    db: Session,
    admin: models.User,
    warehouse_id: int,
    target_type: str,
    target_value: str,
    request: Request,
) -> Tuple[Optional[models.AuditTask], Optional[str]]:
    target_type = target_type.upper().strip()
    target_value = target_value.strip()

    if target_type not in [models.TARGET_LOCATION, models.TARGET_CATEGORY, models.TARGET_SKU]:
        return None, "Invalid target type. Use LOCATION, CATEGORY, or SKU."

    warehouse = db.query(models.Warehouse).filter(models.Warehouse.id == warehouse_id).first()
    if not warehouse:
        return None, "Warehouse not found."

    query = db.query(models.Inventory).filter(models.Inventory.warehouse_id == warehouse_id)

    if target_type == models.TARGET_LOCATION:
        query = query.filter(models.Inventory.shelf_location.ilike(f"%{target_value}%"))
    elif target_type == models.TARGET_CATEGORY:
        query = query.filter(models.Inventory.category.ilike(f"%{target_value}%"))
    elif target_type == models.TARGET_SKU:
        query = query.filter(models.Inventory.item_sku.ilike(f"%{target_value}%"))

    inventory_rows = query.all()
    if not inventory_rows:
        return None, "No inventory rows matched this target. Try Aisle_B, ColdRoom_1, Vegetables, or SKU_TOMATO_001."

    try:
        task = models.AuditTask(
            audit_task_id=generate_audit_task_code(),
            warehouse_id=warehouse_id,
            created_by=admin.id,
            status=models.TASK_ACTIVE,
            target_type=target_type,
            target_value=target_value,
            activated_at=datetime.utcnow(),
        )
        db.add(task)
        db.flush()  # creates task.id before snapshot lines are inserted

        for item in inventory_rows:
            snapshot = models.AuditSnapshotLine(
                audit_task_id=task.id,
                warehouse_id=item.warehouse_id,
                item_sku=item.item_sku,
                item_name=item.item_name,
                shelf_location=item.shelf_location,
                snapshot_quantity=item.quantity,
            )
            db.add(snapshot)

        log_event(
            db=db,
            event_type="TASK_CREATED_WITH_FROZEN_SNAPSHOT",
            request=request,
            user=admin,
            audit_task_id=task.id,
            warehouse_id=warehouse_id,
            commit=False,
        )
        db.commit()
        db.refresh(task)
        return task, None
    except Exception as exc:  # noqa: BLE001 - MVP-friendly rollback
        db.rollback()
        return None, f"Failed to create audit task: {exc}"


def get_auditor_warehouse_ids(db: Session, auditor_id: int) -> List[int]:
    mappings = (
        db.query(models.AuditorWarehouseMapping)
        .filter(
            models.AuditorWarehouseMapping.auditor_id == auditor_id,
            models.AuditorWarehouseMapping.is_active.is_(True),
        )
        .all()
    )
    return [mapping.warehouse_id for mapping in mappings]


def auditor_has_access(db: Session, auditor_id: int, warehouse_id: int) -> bool:
    return (
        db.query(models.AuditorWarehouseMapping)
        .filter(
            models.AuditorWarehouseMapping.auditor_id == auditor_id,
            models.AuditorWarehouseMapping.warehouse_id == warehouse_id,
            models.AuditorWarehouseMapping.is_active.is_(True),
        )
        .first()
        is not None
    )


def get_assigned_warehouses(db: Session, auditor_id: int) -> List[models.Warehouse]:
    warehouse_ids = get_auditor_warehouse_ids(db, auditor_id)
    if not warehouse_ids:
        return []
    return db.query(models.Warehouse).filter(models.Warehouse.id.in_(warehouse_ids)).all()


def get_tasks_for_auditor(db: Session, auditor_id: int) -> List[models.AuditTask]:
    warehouse_ids = get_auditor_warehouse_ids(db, auditor_id)
    if not warehouse_ids:
        return []
    return (
        db.query(models.AuditTask)
        .filter(models.AuditTask.warehouse_id.in_(warehouse_ids))
        .order_by(models.AuditTask.created_at.desc())
        .all()
    )


def get_count_map(db: Session, task_id: int) -> Dict[Tuple[str, str], models.AuditCount]:
    counts = db.query(models.AuditCount).filter(models.AuditCount.audit_task_id == task_id).all()
    return {(count.item_sku, count.shelf_location): count for count in counts}


def submit_count(
    db: Session,
    auditor: models.User,
    task_id: int,
    shelf_location: str,
    item_sku: str,
    location_scan: str,
    sku_scan: str,
    audited_quantity: int,
    request: Request,
) -> Tuple[bool, str]:
    if audited_quantity < 0:
        return False, "Audited quantity cannot be negative."

    task = db.query(models.AuditTask).filter(models.AuditTask.id == task_id).first()
    if not task:
        return False, "Audit task not found."

    if not auditor_has_access(db, auditor.id, task.warehouse_id):
        return False, "Access denied. You are not mapped to this warehouse."

    if task.status == models.TASK_COMPLETED:
        # Still allow viewing completed task, but do not accept modifications.
        existing = (
            db.query(models.AuditCount)
            .filter(
                models.AuditCount.audit_task_id == task_id,
                models.AuditCount.item_sku == item_sku,
                models.AuditCount.shelf_location == shelf_location,
            )
            .first()
        )
        if existing:
            return False, "This count is already submitted and locked."

    snapshot = (
        db.query(models.AuditSnapshotLine)
        .filter(
            models.AuditSnapshotLine.audit_task_id == task_id,
            models.AuditSnapshotLine.item_sku == item_sku,
            models.AuditSnapshotLine.shelf_location == shelf_location,
        )
        .first()
    )
    if not snapshot:
        return False, "This SKU/location is not part of the selected audit task."

    if location_scan.strip() != shelf_location:
        return False, "Location barcode mismatch. Scan/input the exact shelf location shown."

    if sku_scan.strip() != item_sku:
        return False, "SKU scan mismatch. Scan/input the exact SKU shown."

    existing_count = (
        db.query(models.AuditCount)
        .filter(
            models.AuditCount.audit_task_id == task_id,
            models.AuditCount.item_sku == item_sku,
            models.AuditCount.shelf_location == shelf_location,
        )
        .first()
    )
    if existing_count:
        return False, "This shelf/SKU count has already been submitted and cannot be modified."

    try:
        count = models.AuditCount(
            audit_task_id=task_id,
            warehouse_id=task.warehouse_id,
            item_sku=item_sku,
            shelf_location=shelf_location,
            audited_quantity=audited_quantity,
            submitted_by=auditor.id,
            is_locked=True,
        )
        db.add(count)

        if task.status == models.TASK_ACTIVE:
            task.status = models.TASK_IN_PROGRESS

        log_event(
            db=db,
            event_type="LOCATION_UNLOCKED",
            request=request,
            user=auditor,
            audit_task_id=task.id,
            warehouse_id=task.warehouse_id,
            item_sku=item_sku,
            shelf_location=shelf_location,
            commit=False,
        )
        log_event(
            db=db,
            event_type="SKU_SCANNED",
            request=request,
            user=auditor,
            audit_task_id=task.id,
            warehouse_id=task.warehouse_id,
            item_sku=item_sku,
            shelf_location=shelf_location,
            commit=False,
        )
        log_event(
            db=db,
            event_type="COUNT_CONFIRMED_AND_SUBMITTED",
            request=request,
            user=auditor,
            audit_task_id=task.id,
            warehouse_id=task.warehouse_id,
            item_sku=item_sku,
            shelf_location=shelf_location,
            commit=False,
        )

        db.flush()
        total_snapshot_lines = (
            db.query(models.AuditSnapshotLine)
            .filter(models.AuditSnapshotLine.audit_task_id == task_id)
            .count()
        )
        total_submitted_counts = (
            db.query(models.AuditCount)
            .filter(models.AuditCount.audit_task_id == task_id)
            .count()
        )
        if total_snapshot_lines > 0 and total_submitted_counts >= total_snapshot_lines:
            task.status = models.TASK_COMPLETED
            task.completed_at = datetime.utcnow()

        db.commit()
        return True, "Count submitted successfully. This record is now locked."
    except Exception as exc:  # noqa: BLE001 - MVP-friendly rollback
        db.rollback()
        return False, f"Failed to submit count: {exc}"


def get_variance_report_rows(db: Session, task_id: int) -> List[dict]:
    task = db.query(models.AuditTask).filter(models.AuditTask.id == task_id).first()
    if not task:
        return []

    warehouse = db.query(models.Warehouse).filter(models.Warehouse.id == task.warehouse_id).first()
    snapshot_lines = (
        db.query(models.AuditSnapshotLine)
        .filter(models.AuditSnapshotLine.audit_task_id == task_id)
        .order_by(models.AuditSnapshotLine.shelf_location, models.AuditSnapshotLine.item_sku)
        .all()
    )
    count_map = get_count_map(db, task_id)

    rows = []
    for line in snapshot_lines:
        count = count_map.get((line.item_sku, line.shelf_location))
        audited_quantity = count.audited_quantity if count else None

        if audited_quantity is None:
            variance = None
            shrinkage_rate = None
            count_status = "PENDING"
        else:
            variance = audited_quantity - line.snapshot_quantity
            if line.snapshot_quantity == 0:
                shrinkage_rate = None
            else:
                shrinkage_rate = round(
                    ((line.snapshot_quantity - audited_quantity) / line.snapshot_quantity) * 100,
                    2,
                )
            count_status = "SUBMITTED"

        rows.append(
            {
                "Audit_Task_ID": task.audit_task_id,
                "Warehouse_ID": warehouse.warehouse_code if warehouse else str(task.warehouse_id),
                "Item_SKU": line.item_sku,
                "Item_Name": line.item_name,
                "Shelf_Location": line.shelf_location,
                "Snapshot_Quantity": line.snapshot_quantity,
                "Audited_Quantity": audited_quantity,
                "Variance": variance,
                "Shrinkage_Rate": shrinkage_rate,
                "Count_Status": count_status,
            }
        )
    return rows
