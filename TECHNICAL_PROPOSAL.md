# FreshAudit - Technical Proposal

## Objective

FreshAudit is an internal inventory quality and cycle-counting application for fulfillment hubs handling fresh produce. The system allows Central Admins to schedule blind audits and Hub Auditors to physically scan, count, and submit stock quantities without seeing expected stock levels.

The main business goal of this application is to reduce stock inaccuracy caused by spoilage, shrinkage, handling damage, and manual counting bias.

## Proposed MVP

The MVP contains two roles:

1. Central Admin
2. Hub Auditor

Central Admin can create audit tasks, map auditors to warehouses, freeze inventory snapshots, and download variance reports. Hub Auditor can view only assigned warehouse tasks and execute the blind count workflow.

## Architecture

The MVP uses a modular monolithic architecture:

- FastAPI backend
- SQLite database for local demo
- SQLAlchemy ORM
- Jinja2 templates for UI
- Session-based authentication
- CSV report generation

This tech stack/approach was selected for quick development and easy demonstration. For production, the same logical architecture can be deployed with PostgreSQL, Docker, Kubernetes, CI/CD, and observability tools.

## Core Workflow

1. Central Admin logs in.
2. Admin maps auditors to warehouses.
3. Admin creates an audit task by selecting warehouse and target.
4. System freezes matching inventory rows into audit snapshot lines.
5. Hub Auditor logs in.
6. Auditor sees only assigned warehouse audit tasks.
7. Auditor opens task and views shelf location and SKU.
8. Auditor scans/input shelf location to unlock count.
9. Auditor scans/input SKU.
10. Auditor enters physical quantity.
11. Auditor confirms and submits count.
12. Count becomes locked and cannot be edited from auditor device.
13. Admin views/downloads variance report.

## Database Entities

- User
- Warehouse
- AuditorWarehouseMapping
- Inventory
- AuditTask
- AuditSnapshotLine
- AuditCount
- AuditEventLog

## Key Design Decision: Frozen Snapshot

The frozen snapshot is the most important part of the design. When an audit task is activated by the admin, current inventory is copied into `audit_snapshot_lines`. The variance report compares physical count against this fixed snapshot of the inventory, not against live inventory that may change later.

This prevents inaccurate variance reporting caused by inventory movement after audit creation.

## RBAC and Data Isolation

Central Admin has global visibility.

Hub Auditor access is restricted through `auditor_warehouse_mappings`. Every auditor task/count request validates warehouse access on the backend.

Auditor screens do not expose snapshot quantity or variance values.

## Audit Trail

The system logs:

- Login
- Audit task creation
- Location unlock
- SKU scan
- Count confirmation/submission
- Report download
- Auditor warehouse mapping

Each event stores timestamp, user ID, task ID, warehouse ID, IP address, and device details.

## Data Integrity

- Snapshot lines are frozen at audit creation.
- Count submissions are locked.
- Duplicate count submissions are blocked by a unique constraint.
- Unauthorized warehouse access is blocked on backend.
- Report calculation handles division by zero.

## Reporting

Admin variance report includes:

- Audit_Task_ID
- Warehouse_ID
- Item_SKU
- Item_Name
- Shelf_Location
- Snapshot_Quantity
- Audited_Quantity
- Variance
- Shrinkage_Rate
- Count_Status

Shrinkage rate formula:

```text
(snapshot_quantity - audited_quantity) / snapshot_quantity * 100
```

## Reliability and Observability Roadmap

For production, we can add:

- `/health` endpoint for uptime checks
- Prometheus metrics
- Grafana dashboards
- Centralized logging using ELK/OpenSearch
- Alerting for report failures, high variance, and API errors
- RCA support from audit trail logs

Recommended metrics:

- audit_tasks_created_total
- count_submissions_total
- failed_scan_attempts_total
- report_downloads_total
- avg_audit_completion_time
- high_variance_sku_count

## Deployment Roadmap

Production deployment can use:

- Docker image
- Kubernetes Deployment
- Horizontal Pod Autoscaler
- Managed PostgreSQL
- Kubernetes Secrets for credentials
- Ingress for routing
- CI/CD pipeline with automated testing

## Future Enhancements

- Offline-first mobile app/PWA
- Real barcode scanner integration
- Photo evidence for damaged produce
- Approval workflow for inventory adjustment
- Integration with WMS/ERP inventory ledger
- AI anomaly detection for unusual shrinkage patterns
- Auditor productivity dashboard
- Location-level heatmaps for shrinkage-prone zones

## Conclusion

FreshAudit MVP satisfies the core business requirements: RBAC, warehouse isolation, frozen inventory snapshot, blind count workflow, immutable count submission, audit trail, variance report, and CSV export.

The implementation balances speed of delivery with production-readiness and can be scaled with PostgreSQL, Kubernetes, CI/CD, and observability tooling.
