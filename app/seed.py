from sqlalchemy.orm import Session

from app import models
from app.auth import hash_password


def seed_data(db: Session) -> None:
    """Seed demo data once. Safe to run every app startup."""
    if db.query(models.User).count() > 0:
        return

    admin = models.User(
        name="Central Admin",
        email="admin@freshaudit.com",
        password_hash=hash_password("admin123"),
        role=models.ROLE_ADMIN,
    )
    auditor1 = models.User(
        name="Hub Auditor BLR",
        email="auditor1@freshaudit.com",
        password_hash=hash_password("auditor123"),
        role=models.ROLE_AUDITOR,
    )
    auditor2 = models.User(
        name="Hub Auditor HYD",
        email="auditor2@freshaudit.com",
        password_hash=hash_password("auditor123"),
        role=models.ROLE_AUDITOR,
    )
    db.add_all([admin, auditor1, auditor2])
    db.flush()

    blr = models.Warehouse(
        warehouse_code="WH_BLR_001",
        warehouse_name="Bengaluru Fresh Hub",
        city="Bengaluru",
    )
    hyd = models.Warehouse(
        warehouse_code="WH_HYD_001",
        warehouse_name="Hyderabad Fresh Hub",
        city="Hyderabad",
    )
    db.add_all([blr, hyd])
    db.flush()

    db.add_all(
        [
            models.AuditorWarehouseMapping(auditor_id=auditor1.id, warehouse_id=blr.id),
            models.AuditorWarehouseMapping(auditor_id=auditor2.id, warehouse_id=hyd.id),
        ]
    )

    inventory_rows = [
        # Bengaluru warehouse inventory
        models.Inventory(
            warehouse_id=blr.id,
            item_sku="SKU_TOMATO_001",
            item_name="Tomato 1kg Pack",
            category="Vegetables",
            shelf_location="Aisle_B-Bay_12-Shelf_1",
            quantity=100,
        ),
        models.Inventory(
            warehouse_id=blr.id,
            item_sku="SKU_POTATO_001",
            item_name="Potato 1kg Pack",
            category="Vegetables",
            shelf_location="Aisle_B-Bay_12-Shelf_2",
            quantity=150,
        ),
        models.Inventory(
            warehouse_id=blr.id,
            item_sku="SKU_ONION_001",
            item_name="Onion 1kg Pack",
            category="Vegetables",
            shelf_location="Aisle_B-Bay_13-Shelf_1",
            quantity=80,
        ),
        models.Inventory(
            warehouse_id=blr.id,
            item_sku="SKU_APPLE_001",
            item_name="Apple 500g Pack",
            category="Fruits",
            shelf_location="ColdRoom_1-Shelf_1",
            quantity=60,
        ),
        models.Inventory(
            warehouse_id=blr.id,
            item_sku="SKU_BANANA_001",
            item_name="Banana 1 Dozen",
            category="Fruits",
            shelf_location="ColdRoom_1-Shelf_2",
            quantity=120,
        ),
        models.Inventory(
            warehouse_id=blr.id,
            item_sku="SKU_SPINACH_001",
            item_name="Spinach Bunch",
            category="Leafy Greens",
            shelf_location="ColdRoom_2-Shelf_1",
            quantity=45,
        ),
        # Hyderabad warehouse inventory
        models.Inventory(
            warehouse_id=hyd.id,
            item_sku="SKU_TOMATO_001",
            item_name="Tomato 1kg Pack",
            category="Vegetables",
            shelf_location="Aisle_A-Bay_01-Shelf_1",
            quantity=90,
        ),
        models.Inventory(
            warehouse_id=hyd.id,
            item_sku="SKU_CARROT_001",
            item_name="Carrot 500g Pack",
            category="Vegetables",
            shelf_location="Aisle_A-Bay_02-Shelf_1",
            quantity=110,
        ),
        models.Inventory(
            warehouse_id=hyd.id,
            item_sku="SKU_GRAPES_001",
            item_name="Grapes 500g Pack",
            category="Fruits",
            shelf_location="ColdRoom_1-Shelf_1",
            quantity=70,
        ),
        models.Inventory(
            warehouse_id=hyd.id,
            item_sku="SKU_MANGO_001",
            item_name="Mango 1kg Pack",
            category="Fruits",
            shelf_location="ColdRoom_1-Shelf_2",
            quantity=55,
        ),
    ]
    db.add_all(inventory_rows)
    db.commit()
