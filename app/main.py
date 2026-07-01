from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, SessionLocal, engine
from app.routes_admin import router as admin_router
from app.routes_auditor import router as auditor_router
from app.routes_auth import router as auth_router
from app.seed import seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables and insert demo data when the app starts.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="FreshAudit", version="1.0.0", lifespan=lifespan)

# Session-based auth for quick assessment demo.
# Production: move this secret to an environment variable/secret manager.
app.add_middleware(
    SessionMiddleware,
    secret_key="change-this-secret-in-production",
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(auditor_router)


@app.get("/health")
def health_check():
    return {"status": "UP", "service": "FreshAudit"}
