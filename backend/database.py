"""Database layer for the UnderCover backend."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("DB_PATH", "undercover.db")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_db_path() -> str:
    """Return the current database path."""
    return os.getenv("DB_PATH", DB_PATH)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    path = db_path if db_path is not None else get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> None:
    """Initialize database tables."""
    path = db_path if db_path is not None else get_db_path()
    with get_connection(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                submitted_on TEXT NOT NULL,
                incident_date TEXT NOT NULL,
                incident_location TEXT NOT NULL,
                summary TEXT NOT NULL,
                story TEXT NOT NULL,
                amount_claimed REAL NOT NULL,
                items TEXT NOT NULL,
                documents TEXT NOT NULL,
                status TEXT NOT NULL,
                decision TEXT,
                payout REAL,
                reason TEXT,
                policy_section TEXT,
                paid INTEGER NOT NULL DEFAULT 0,
                signed_off INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS policies (
                policy_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                plan TEXT NOT NULL,
                add_ons TEXT NOT NULL,
                purchased_on TEXT NOT NULL,
                sold_through TEXT NOT NULL,
                trip TEXT NOT NULL,
                travelers TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                date_of_birth TEXT NOT NULL,
                address TEXT NOT NULL,
                customer_since TEXT NOT NULL,
                previous_claims TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plans (
                plan TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS company (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL
            );
        """)


def _seed_claims(conn: sqlite3.Connection) -> None:
    path = DATA_DIR / "claims.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for c in data:
        conn.execute(
            """
            INSERT INTO claims (
                claim_id, policy_id, customer_id, claim_type, submitted_on,
                incident_date, incident_location, summary, story,
                amount_claimed, items, documents, status, paid, signed_off
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, 0)
            """,
            (
                c["claim_id"],
                c["policy_id"],
                c["customer_id"],
                c["claim_type"],
                c["submitted_on"],
                c["incident_date"],
                c["incident_location"],
                c["summary"],
                c["story"],
                c["amount_claimed"],
                json.dumps(c.get("items", [])),
                json.dumps(c.get("documents", [])),
            ),
        )


def _seed_policies(conn: sqlite3.Connection) -> None:
    path = DATA_DIR / "policies.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for p in data:
        conn.execute(
            """
            INSERT INTO policies (
                policy_id, customer_id, plan, add_ons, purchased_on,
                sold_through, trip, travelers, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["policy_id"],
                p["customer_id"],
                p["plan"],
                json.dumps(p.get("add_ons", [])),
                p["purchased_on"],
                p["sold_through"],
                json.dumps(p.get("trip", {})),
                json.dumps(p.get("travelers", [])),
                p["status"],
            ),
        )


def _seed_customers(conn: sqlite3.Connection) -> None:
    path = DATA_DIR / "customers.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for cust in data:
        conn.execute(
            """
            INSERT INTO customers (
                customer_id, name, email, phone, date_of_birth,
                address, customer_since, previous_claims
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cust["customer_id"],
                cust["name"],
                cust["email"],
                cust["phone"],
                cust["date_of_birth"],
                json.dumps(cust.get("address", {})),
                cust["customer_since"],
                json.dumps(cust.get("previous_claims", [])),
            ),
        )


def _seed_plans_and_company(conn: sqlite3.Connection) -> None:
    plans_path = DATA_DIR / "plans.json"
    if plans_path.exists():
        with open(plans_path, encoding="utf-8") as f:
            plans_data = json.load(f)
        for plan_info in plans_data.get("plans", []):
            conn.execute(
                "INSERT INTO plans (plan, data) VALUES (?, ?)",
                (plan_info["plan"], json.dumps(plan_info)),
            )

    company_path = DATA_DIR / "company.json"
    if company_path.exists():
        with open(company_path, encoding="utf-8") as f:
            company_data = json.load(f)
        for k, v in company_data.items():
            conn.execute(
                "INSERT INTO company (key, value) VALUES (?, ?)",
                (k, json.dumps(v)),
            )


def seed_db(db_path: str | None = None) -> None:
    """Seed the database from data files."""
    path = db_path if db_path is not None else get_db_path()
    init_db(path)
    with get_connection(path) as conn:
        conn.execute("DELETE FROM claims")
        conn.execute("DELETE FROM policies")
        conn.execute("DELETE FROM customers")
        conn.execute("DELETE FROM plans")
        conn.execute("DELETE FROM company")
        conn.execute("DELETE FROM activities")

        _seed_claims(conn)
        _seed_policies(conn)
        _seed_customers(conn)
        _seed_plans_and_company(conn)


def get_policy_wording_text() -> str:
    """Return the policy wording text."""
    path = DATA_DIR / "policy_wording.md"
    with open(path, encoding="utf-8") as f:
        return f.read()


def format_claim_row(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a claim database row to a dictionary."""
    data = dict(row)
    data["items"] = json.loads(data["items"])
    data["documents"] = json.loads(data["documents"])
    data["paid"] = bool(data["paid"])
    data["signed_off"] = bool(data["signed_off"])
    return data
