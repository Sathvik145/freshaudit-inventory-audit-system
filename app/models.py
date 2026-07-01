from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


ROLE_ADMIN = "CENTRAL_ADMIN"
ROLE_AUDITOR = "HUB_AUDITOR"

TASK_ACTIVE = "ACTIVE"
TASK_IN_PROGRESS = "IN_PROGRESS"
TASK_COMPLETED = "COMPLETED"

TARGET_LOCATION = "LOCATION"
TARGET_CATEGORY = "CATEGORY"
TARGET_SKU = "SKU"


def utc_now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(40), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    created_tasks = relationship("AuditTask", back_populates="creator")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_code = Column(String(50), unique=True, index=True, nullable=False)
    warehouse_name = Column(String(150), nullable=False)
    city = Column(String(80), nullable=False)
    status = Column(String(30), default="ACTIVE", nullable=False)

    inventory_items = relationship("Inventory", back_populates="warehouse")
    audit_tasks = relationship("AuditTask", back_populates="warehouse")


class AuditorWarehouseMapping(Base):
    __tablename__ = "auditor_warehouse_mappings"

    id = Column(Integer, primary_key=True, index=True)
    auditor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("auditor_id", "warehouse_id", name="uq_auditor_warehouse"),
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    item_sku = Column(String(80), nullable=False)
    item_name = Column(String(150), nullable=False)
    category = Column(String(80), nullable=False)
    shelf_location = Column(String(120), nullable=False)
    quantity = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utc_now, nullable=False)

    warehouse = relationship("Warehouse", back_populates="inventory_items")


class AuditTask(Base):
    __tablename__ = "audit_tasks"

    id = Column(Integer, primary_key=True, index=True)
    audit_task_id = Column(String(80), unique=True, index=True, nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(40), default=TASK_ACTIVE, nullable=False)
    target_type = Column(String(40), nullable=False)
    target_value = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    activated_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    warehouse = relationship("Warehouse", back_populates="audit_tasks")
    creator = relationship("User", back_populates="created_tasks")
    snapshot_lines = relationship("AuditSnapshotLine", back_populates="task")
    counts = relationship("AuditCount", back_populates="task")


class AuditSnapshotLine(Base):
    __tablename__ = "audit_snapshot_lines"

    id = Column(Integer, primary_key=True, index=True)
    audit_task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    item_sku = Column(String(80), nullable=False)
    item_name = Column(String(150), nullable=False)
    shelf_location = Column(String(120), nullable=False)
    snapshot_quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    task = relationship("AuditTask", back_populates="snapshot_lines")


class AuditCount(Base):
    __tablename__ = "audit_counts"

    id = Column(Integer, primary_key=True, index=True)
    audit_task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    item_sku = Column(String(80), nullable=False)
    shelf_location = Column(String(120), nullable=False)
    audited_quantity = Column(Integer, nullable=False)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, default=utc_now, nullable=False)
    is_locked = Column(Boolean, default=True, nullable=False)

    task = relationship("AuditTask", back_populates="counts")

    __table_args__ = (
        UniqueConstraint(
            "audit_task_id",
            "item_sku",
            "shelf_location",
            name="uq_task_sku_location_count",
        ),
    )


class AuditEventLog(Base):
    __tablename__ = "audit_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    audit_task_id = Column(Integer, ForeignKey("audit_tasks.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String(80), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    item_sku = Column(String(80), nullable=True)
    shelf_location = Column(String(120), nullable=True)
    ip_address = Column(String(80), nullable=True)
    device_info = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
