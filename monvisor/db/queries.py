"""
monvisor/db/queries.py
Typed query functions for all database operations.
"""

import json
from datetime import datetime
from typing import Optional
from monvisor.db.schema import get_conn


# ── Environments ──────────────────────────────────────────────────────────────

def create_environment(name: str, prometheus_url: str = None, grafana_url: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO environments (name, prometheus_url, grafana_url) VALUES (?,?,?)",
            (name, prometheus_url, grafana_url)
        )
        return cur.lastrowid


def get_environment(name: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM environments WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None


def get_environment_by_id(env_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM environments WHERE id=?", (env_id,)).fetchone()
        return dict(row) if row else None


def list_environments() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM environments ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def update_environment(name: str, prometheus_url: str = None, grafana_url: str = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE environments SET prometheus_url=?, grafana_url=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
            (prometheus_url, grafana_url, name)
        )


# ── CIDRs ─────────────────────────────────────────────────────────────────────

def add_cidr(env_id: int, cidr: str, label: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO cidrs (env_id, cidr, label) VALUES (?,?,?)",
            (env_id, cidr, label)
        )
        return cur.lastrowid


def get_cidrs(env_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cidrs WHERE env_id=? ORDER BY cidr", (env_id,)).fetchall()
        return [dict(r) for r in rows]


# ── Discoveries ───────────────────────────────────────────────────────────────

def create_discovery(env_id: int, cidr: str, raw_findings: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO discoveries (env_id, cidr, host_count, raw_findings) VALUES (?,?,?,?)",
            (env_id, cidr, len(raw_findings.get("hosts", [])), json.dumps(raw_findings))
        )
        return cur.lastrowid


def get_latest_discovery(env_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM discoveries WHERE env_id=? ORDER BY scan_time DESC LIMIT 1",
            (env_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["raw_findings"] = json.loads(d["raw_findings"]) if d["raw_findings"] else {}
            return d
        return None


# ── Services ──────────────────────────────────────────────────────────────────

def upsert_service(discovery_id: int, env_id: int, host: str, port: int,
                   service_type: str, version: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO services (discovery_id, env_id, host, port, service_type, version)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(env_id, host, port) DO UPDATE SET
                discovery_id=excluded.discovery_id,
                service_type=excluded.service_type,
                version=excluded.version
        """, (discovery_id, env_id, host, port, service_type, version))
        return cur.lastrowid


def get_services(env_id: int, undecided_only: bool = False) -> list:
    with get_conn() as conn:
        if undecided_only:
            rows = conn.execute(
                "SELECT * FROM services WHERE env_id=? AND monitor IS NULL ORDER BY host, port",
                (env_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM services WHERE env_id=? ORDER BY host, port",
                (env_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_monitored_services(env_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM services WHERE env_id=? AND monitor=1 ORDER BY service_type, host",
            (env_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def set_service_decision(service_id: int, monitor: bool, notes: str = None,
                         monitor_mode: str = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE services SET monitor=?, notes=?, monitor_mode=?, decided_at=CURRENT_TIMESTAMP WHERE id=?",
            (1 if monitor else 0, notes, monitor_mode, service_id)
        )


# ── Configs ───────────────────────────────────────────────────────────────────

def save_config(env_id: int, config_type: str, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO configs (env_id, config_type, content) VALUES (?,?,?)",
            (env_id, config_type, content)
        )
        return cur.lastrowid


def get_latest_config(env_id: int, config_type: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM configs WHERE env_id=? AND config_type=? ORDER BY generated_at DESC LIMIT 1",
            (env_id, config_type)
        ).fetchone()
        return dict(row) if row else None


def list_configs(env_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, config_type, generated_at, deployed_at FROM configs WHERE env_id=? ORDER BY generated_at DESC",
            (env_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = None) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (key, value)
        )


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(token: str, expires_at: datetime):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, expires_at) VALUES (?,?)",
            (token, expires_at.isoformat())
        )


def validate_session(token: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id=? AND expires_at > CURRENT_TIMESTAMP",
            (token,)
        ).fetchone()
        return row is not None


def delete_session(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (token,))
