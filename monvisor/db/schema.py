# MonVisor — AI-assisted monitoring configuration for Prometheus/Grafana.
# Copyright (C) 2026 James Sparenberg
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
monvisor/db/schema.py
SQLite schema creation and migration.
"""

import sqlite3
from pathlib import Path
from monvisor.config import DB_PATH


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS environments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    prometheus_url  TEXT,
    grafana_url     TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cidrs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    env_id      INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    cidr        TEXT NOT NULL,
    label       TEXT,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(env_id, cidr)
);

CREATE TABLE IF NOT EXISTS discoveries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    env_id       INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    cidr         TEXT NOT NULL,
    scan_time    DATETIME DEFAULT CURRENT_TIMESTAMP,
    host_count   INTEGER DEFAULT 0,
    raw_findings TEXT
);

CREATE TABLE IF NOT EXISTS services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discovery_id    INTEGER NOT NULL REFERENCES discoveries(id) ON DELETE CASCADE,
    env_id          INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL,
    service_type    TEXT,
    version         TEXT,
    monitor         INTEGER DEFAULT NULL,  -- NULL=undecided 1=yes 0=no
    monitor_mode    TEXT DEFAULT NULL,     -- NULL/'exporter'=scrape, 'blackbox'=remote probe
    notes           TEXT,
    decided_at      DATETIME,
    UNIQUE(env_id, host, port)
);

CREATE TABLE IF NOT EXISTS configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    env_id          INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    config_type     TEXT NOT NULL,         -- prometheus, alertmanager, rules
    content         TEXT NOT NULL,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    deployed_at     DATETIME,
    deployed_by     TEXT
);

CREATE TABLE IF NOT EXISTS dashboards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    env_id          INTEGER NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    source          TEXT NOT NULL,         -- stock, generated
    service_type    TEXT,
    content         TEXT NOT NULL,         -- Grafana dashboard JSON
    provisioned_at  DATETIME
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,          -- UUID token
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL,
    user        TEXT DEFAULT 'admin'
);

CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn() -> sqlite3.Connection:
    """Get a database connection with row factory set."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create all tables if they don't exist, then apply in-place migrations."""
    conn = get_conn()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """Additive, idempotent migrations for existing databases.
    Only ever ADDs columns/tables — never drops or rewrites — so a live
    state.db keeps all its data."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(services)").fetchall()]
    if "monitor_mode" not in cols:
        # NULL/'exporter' = scrape its own metrics; 'blackbox' = remote probe
        # (host where an exporter cannot be installed).
        conn.execute("ALTER TABLE services ADD COLUMN monitor_mode TEXT DEFAULT NULL")
