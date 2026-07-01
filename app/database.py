from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# We used SQLite is used for the local assessment demo.
# For production replacement we can use PostgreSQL URL, e.g.
# postgresql+psycopg2://user:password@host:5432/freshaudit
SQLALCHEMY_DATABASE_URL = "sqlite:///./freshaudit.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
