"""
Simple Transaction API
-----------------------
FastAPI service that writes/reads "transaction" records to/from PostgreSQL.
Everything is kept in one file on purpose (task requirement: no over-engineering).
"""

import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# --------------------------------------------------------------------------
# Database configuration
# --------------------------------------------------------------------------
# DATABASE_URL is injected by docker-compose (see docker-compose.yml).
# The "host" part of this URL is the DB container's service name, e.g. "db".
# Inside the docker-compose network, "db" resolves via Docker's embedded DNS
# to the database container -> this IS the FQDN-based connection.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://app_user:app_pass@db:5432/transactions_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# --------------------------------------------------------------------------
# DB model
# --------------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String(100), nullable=False)
    receiver = Column(String(100), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------
# API schemas (request/response)
# --------------------------------------------------------------------------
class TransactionCreate(BaseModel):
    sender: str = Field(..., min_length=1, max_length=100)
    receiver: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)


class TransactionOut(BaseModel):
    id: int
    sender: str
    receiver: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(title="Transaction API", version="1.0.0")


def wait_for_db(retries: int = 10, delay: float = 2.0):
    """Retry loop so the API doesn't crash-loop while Postgres is booting."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect():
                return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay)


@app.on_event("startup")
def on_startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    """Used by Docker HEALTHCHECK and for manual checks."""
    try:
        with engine.connect():
            return {"status": "ok"}
    except OperationalError:
        raise HTTPException(status_code=503, detail="database unavailable")


@app.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate):
    db = SessionLocal()
    try:
        tx = Transaction(
            sender=payload.sender,
            receiver=payload.receiver,
            amount=payload.amount,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx
    finally:
        db.close()


@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions():
    db = SessionLocal()
    try:
        return db.query(Transaction).order_by(Transaction.id.desc()).all()
    finally:
        db.close()


@app.get("/transactions/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int):
    db = SessionLocal()
    try:
        tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            raise HTTPException(status_code=404, detail="transaction not found")
        return tx
    finally:
        db.close()
