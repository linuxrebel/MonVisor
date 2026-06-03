# MonVisor — Architectural Roadmap
# Last updated: 2026-06-03
# Purpose: Forward-looking architecture for Phases 4.7–4.12.
#          These phases strengthen the free-tier core before Phase 5 (paid).
#          Read alongside ENGINEERING_MAP.md and PROJECT_STATE.md.

---

## Product Philosophy

MonVisor is a **monitoring lifecycle management assistant**, not a continuous
network monitor. The guiding principle is: **meet the user where they are, then
help them get where they need to go.** We do not tear down existing infrastructure
and rebuild it our way.

This means:

- Users with nothing get a guided greenfield path.
- Users with an existing Prometheus stack hand us their config and we build from it.
- We always propose, never apply without consent.
- We never make noise on a network without the user explicitly asking.
- Once the initial inventory is built, the user owns it. We assist on demand.

MonVisor runs on **its own dedicated box or VM**, separate from the existing
monitoring stack. This is not optional — it is the deployment model. The user's
existing Prometheus/Alertmanager/Grafana stack is untouched until they decide
to cut over.

---

## Deployment Model

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│   EXISTING MONITORING BOX   │     │      MONVISOR BOX / VM      │
│                             │     │                             │
│  Prometheus (existing)      │     │  MonVisor                   │
│  Alertmanager (existing)    │     │  Prometheus (managed)       │
│  Grafana (existing)         │     │  Alertmanager (suppressed)  │
│                             │     │  Grafana (managed)          │
│  Config: user owns it       │     │  Ollama + Gemma4            │
│  Alerts: going to oncall    │     │  ChromaDB                   │
└─────────────────────────────┘     │  SQLite inventory           │
                                    │  Synthetic test runner      │
         User decides cutover  ←────│                             │
         on their own timeline      └─────────────────────────────┘
```

**Alert suppression by default.** MonVisor's Alertmanager ships configured with
a null receiver. Alerts fire internally and are visible in the MonVisor UI but
nothing goes out to humans until the user explicitly enables a notification channel:

```
monvisor alerting enable pagerduty --integration-key <key>
monvisor alerting enable email --smtp-host <host> ...
monvisor alerting enable slack --webhook <url>
```

**Phased cutover.** MonVisor tracks and prompts for four phases. It never
advances a phase without explicit user confirmation:

```
Phase 1: MonVisor scraping all targets. Alerts suppressed. User watching dashboards.
Phase 2: User enables alerting to low-stakes channel (Slack dev room, test email).
Phase 3: User validates alert quality over N days of their choosing.
Phase 4: User enables production alerting. Decommissions old stack. Their call, their timeline.
```

Phase state is stored in config.yml. The MonVisor UI surfaces the current phase
and the next step, but never rushes the user.

---

## Entry Points

### Entry Point A — Greenfield

User has no existing Prometheus setup. MonVisor scans the network once (the
user's one-time security window), builds the inventory, generates configs, user
ratifies. From then on the inventory is user-owned and user-maintained.

```
monvisor init
monvisor scan <env>           ← one-time, requires security window
monvisor review <env>
monvisor generate <env>
→ inventory established, user owns it from here
```

Future changes: `monvisor scan <env> --host <ip>` only. No automatic rescans.

### Entry Point B — Brownfield

User has an existing prometheus.yml. They hand it to MonVisor:

```
monvisor import --prometheus-config /path/to/prometheus.yml
monvisor import --alertmanager-config /path/to/alertmanager.yml  # optional
monvisor import --grafana-url http://grafana:3000 --grafana-token <token>  # optional
```

MonVisor parses the existing config, extracts scrape targets, builds the hosts
and services inventory from what is already there. No network scan is triggered.
The existing config is the source of truth.

Import is **non-destructive**:
- The original file is never modified or moved.
- MonVisor reads it, builds internal state, and works from that baseline.
- The user's config remains authoritative until they explicitly ask MonVisor to
  generate a replacement.

**Partial imports are expected and handled.** A real prometheus.yml often has
IPs with no hostnames, jobs with no metadata, static configs from years ago.
MonVisor imports what it can parse cleanly, flags what it cannot resolve, and
lets the user fill gaps — it does not fail on incomplete data.

---

## Inventory Ownership Model

Discovery exists to **bootstrap the inventory once**. After that:

- No automatic rescans. Ever.
- No background scanning. Ever.
- The inventory is a database the user maintains, not a live view of the network.
- `monvisor scan <env>` warns if the environment already has a completed scan.
- Future scanning is always targeted: `monvisor scan <env> --host <ip|cidr>`

**Host lifecycle states:**

```
pending     → discovered or imported, not yet reviewed by user
configured  → user has reviewed, config generated, in active inventory
missing     → user-targeted rescan requested, host did not respond
forgotten   → user marked as "removed by design", never surfaces again
```

When a targeted rescan finds a host missing:

```
⚠  192.168.1.33  (QNAP NAS, last seen 2026-05-28)  — not responding

   What happened to this host?
   [1] Temporarily offline — keep watching
   [2] Decommissioned / removed — forget it
   [3] IP reassigned — I'll add the new IP manually
```

Option 2 sets status = 'forgotten'. The record is never shown again.

---

## Phase 4.7 — AI Intelligence: General Answers + Web Learning

### Problem

`ask` today refuses anything outside the corpus. Users asking legitimate
Prometheus/Grafana/Alertmanager questions get "I've not yet learned how to do
that." This is the opposite of useful.

### Three-Tier Answer Strategy

```
User question
     │
     ▼
Tier 1: RAG retrieval (existing)
     │   Distance ≤ 0.40 AND LLM confirms relevance?
     ├── HIT  → grounded answer from corpus, labelled as such
     └── MISS
          │
          ▼
     Tier 2: General domain LLM (new)
          │   Question within {prometheus, alertmanager, grafana, exporters,
          │   promql, recording rules, alerting, scrape configs}?
          ├── HIT  → Ollama with domain system prompt
          │         labelled: [General knowledge — not from knowledge base]
          └── MISS
                   │
                   ▼
              Tier 3: Web fetch or guided search (new)
```

**Domain system prompt (stored in rag/prompts.py):**
```
You are a Prometheus, Grafana, and Alertmanager expert. Answer accurately
and concisely. If uncertain, say so. Do not invent configuration syntax.
Prefer working YAML/PromQL examples where applicable.
```

### Web Fetch Pipeline

**No Playwright as a hard dependency.** Playwright is a headless browser —
correct for JS-rendered SPAs, wrong for documentation pages and GitHub READMEs.
The install weight (~150MB of Chromium) is unacceptable on a monitoring server.

Primary path: `httpx GET → trafilatura.extract() → clean text → embed → store`

`trafilatura` strips navigation/ads/boilerplate from HTML and returns clean
article text. Handles 95% of useful documentation pages without a browser.

Playwright is an optional extra:
```toml
[project.optional-dependencies]
browser = ["playwright>=1.40"]
```
The fetch layer checks for Playwright at runtime and falls back to
httpx+trafilatura if absent.

**Web fetch is opt-in.** Disabled by default. Enabled at `monvisor init` or
via config.yml. Nothing is sent anywhere other than the URLs fetched.

### Offline / Air-Gap Fallback

If web fetch is disabled or fails:

```
─────────────────────────────────────────────────────────────────
I can't reach the web to look this up. To find this yourself:

Suggested search:  prometheus remote_write thanos receiver config
Suggested sites:
  • https://prometheus.io/docs/prometheus/latest/configuration/
  • https://thanos.io/tip/components/receive.md/

Paste the relevant content here and I'll work with it.
─────────────────────────────────────────────────────────────────
```

Pasted content is used in the current session only (not persisted to `learned`)
unless the user runs `monvisor knowledge add --text <file>`.

### `learned` ChromaDB Collection

New third collection alongside `pairs` and `exemplars`. Runtime only — not
part of the shipped knowledge package.

Metadata per document:
```python
{
  "source_url":   "https://prometheus.io/docs/...",
  "fetched_at":   "2026-06-03T14:22:00Z",
  "content_hash": "sha256:...",      # dedup key
  "ttl_days":     7,                 # configurable
  "origin":       "web_fetch" | "user_paste" | "knowledge_add",
  "stale":        False,
}
```

Staleness: entries older than ttl_days are flagged stale (not deleted) and
de-prioritised in ranking. `monvisor knowledge refresh` re-fetches stale entries.
`monvisor knowledge prune --days 30` drops old entries to prevent unbounded growth.
`monvisor knowledge status` reports: pairs / exemplars / learned (N docs, M stale).

### New Files (4.7)

```
monvisor/rag/fetch.py       ← httpx + trafilatura; Playwright optional fallback
monvisor/rag/learn.py       ← ingest into 'learned'; dedup; TTL management
monvisor/rag/prompts.py     ← ALL prompt strings (centralised)
```

### New Dependencies (4.7)

```toml
"trafilatura>=1.8",   # HTML content extraction
# optional: "playwright>=1.40"  via monvisor[browser]
```

---

## Phase 4.8a — Interactive Configuration (`monvisor configure`)

### Problem

`monvisor generate` is batch and one-shot. Services on appliances with no
exporter, custom apps, SNMP-only devices, and HTTP endpoints with proprietary
JSON have no path from discovery to working scrape config.

### Agent Loop

```
monvisor configure <env> <host>
  → Load host record + existing services from inventory
  → Build context: IP, open ports, hostname, existing fingerprint, env name
  → Enter REPL loop (max 8 turns, configurable):

      Gemma4 asks one clarifying question at a time
      User answers
      Gemma4: next question OR emit [READY_TO_GENERATE]

  → On [READY_TO_GENERATE]: exit loop, generate YAML fragment
  → Validate (promtool if prometheus type)
  → Write to ~/.monvisor/configs/<env>-<host>-custom-<timestamp>.yml
  → Offer to merge into environment's main prometheus.yml
```

**Available strategies Gemma4 can recommend:**
node_exporter, blackbox HTTP/TCP/ICMP probe, SNMP exporter, custom HTTP
metrics endpoint, pushgateway, synthetic test (routes to 4.8b).

**Conversation persistence:** On exit the user is asked:
```
Save this session as a knowledge pair? [Y/n]
```
If yes, written to `~/.monvisor/learned_configure/` for future corpus inclusion.
User sessions grow the system's configure knowledge over time.

### New Files (4.8a)

```
monvisor/cli/configure.py   ← agent loop, conversation history, signal detection
```

---

## Phase 4.8b — Synthetic Monitoring

### Problem

Complex multi-step application workflows cannot be monitored by a single
blackbox probe. A checkout flow, login sequence, or API transaction chain has
multiple potential failure points — each one needs its own metric and alert.

### In-House Synthetic Runner

MonVisor ships its own lightweight synthetic test runner (Python, no external
test framework required). The `monvisor configure` loop has a synthetic branch:
when the service is an application with a user-facing workflow, Gemma4 shifts
into synthetic test design mode.

**Test definition (YAML, generated by configure):**
```yaml
synthetic_test:
  name: checkout_flow
  interval: 60s
  timeout: 30s
  steps:
    - name: login
      type: http_post
      url: https://app.example.com/login
      body: '{"user":"probe","pass":"${SYNTH_PASS}"}'
      expect_status: 200
      expect_body_contains: "token"
      extract: {token: "$.token"}

    - name: add_to_cart
      type: http_post
      url: https://app.example.com/cart
      headers: {Authorization: "Bearer ${token}"}
      expect_status: 200

    - name: checkout
      type: http_post
      url: https://app.example.com/checkout
      headers: {Authorization: "Bearer ${token}"}
      expect_status: 201
```

**Metrics emitted per step:**
```
monvisor_synthetic_step_duration_seconds{test,step}
monvisor_synthetic_step_success{test,step}          0|1
monvisor_synthetic_test_success{test}               0|1
monvisor_synthetic_test_last_run_timestamp{test}
```

The runner exposes a /metrics endpoint (default :9399) that Prometheus scrapes
like any other target. It is a long-running process managed as a systemd unit,
started by `monvisor synthetic start`.

**Alert rules are generated automatically** for each synthetic test:
any step failure sustained for 2 minutes triggers an alert.

**Secrets** (passwords, tokens used in test steps) are stored in
`~/.monvisor/synthetic_secrets/` with 0600 permissions, never in the test
definition YAML.

### New Files (4.8b)

```
monvisor/synthetic/
├── runner.py       ← test execution engine, step types, secret injection
├── exporter.py     ← Prometheus metrics endpoint (:9399)
└── schema.py       ← test definition YAML validation
monvisor/cli/synthetic.py   ← start/stop/list/status commands
```

---

## Phase 4.9 — Network Discovery Overhaul

### Scan Philosophy

One-time. Conservative. User-initiated only.

MonVisor gets one security window to scan. After initial inventory is built,
all future scanning is targeted and on-demand: `monvisor scan <env> --host <ip>`.

### Two-Pass Strategy

**Pass 1 — Host discovery (fast, broad, conservative)**

Goal: find every live IP before committing to a service scan.

```
nmap -sn                 # ping sweep: ICMP echo + TCP SYN 80/443
     -PE -PP -PM         # ICMP echo, timestamp, netmask variants
     -T3                 # polite timing (never T4/T5)
     <cidr>
```

Also (where available and appropriate):
- ARP via scapy (optional dep): same-subnet only. If the CIDR routes through
  a gateway (i.e. not directly attached), ARP is skipped — it's inappropriate
  on routed networks and will alarm security teams.
- mDNS: passive listen via avahi-browse if avahi-daemon is running. No active
  mDNS flooding.

**Pass 2 — Service scan (targeted, confirmed-live hosts only)**

```
nmap -sS (if root/cap_net_raw) or -sT (fallback)
     -sV
     -T3
     -p <expanded port list>
     <confirmed-live-ips>
```

Expanded port list adds: 80, 443, 554/8554 (RTSP cameras), 161 (SNMP),
5353 (mDNS confirm), 8888, 5000, 5001, 8880.

**Root/capability advisory (once per scan, not per command):**
```
ℹ  Running without raw socket access. Some hosts may be missed.
   For best results:  sudo monvisor scan <env>
   Or:                sudo setcap cap_net_raw+ep $(which nmap)
```

**Security posture:**
- Default timing: -T3 (polite). Never expose -T4/-T5 to users.
- ARP only on directly-attached subnets.
- mDNS passive only.
- No OS detection (-O) — noisy, not needed.
- No aggressive parallelism defaults.

### `hosts` Table

```sql
CREATE TABLE hosts (
    id              INTEGER PRIMARY KEY,
    env_id          INTEGER REFERENCES environments(id),
    ip              TEXT NOT NULL,
    mac             TEXT,
    vendor          TEXT,                   -- OUI lookup
    hostname        TEXT,                   -- reverse DNS or mDNS
    device_type     TEXT,                   -- 'printer','camera','router',
                                            --  'server','workstation','iot','unknown'
    scan_status     TEXT DEFAULT 'pending', -- 'pending','configured','missing','forgotten'
    -- Probe response profile
    responds_icmp   BOOLEAN DEFAULT NULL,
    responds_arp    BOOLEAN DEFAULT NULL,
    responds_tcp80  BOOLEAN DEFAULT NULL,
    responds_tcp443 BOOLEAN DEFAULT NULL,
    responds_snmp   BOOLEAN DEFAULT NULL,
    responds_mdns   BOOLEAN DEFAULT NULL,
    -- Scan history
    first_seen      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen       DATETIME,
    scan_count      INTEGER DEFAULT 0,
    -- User notes
    notes           TEXT,
    UNIQUE(env_id, ip)
);
```

**OUI vendor lookup:** bundled `monvisor/data/oui_mini.json` (~40KB, top 2000
vendors, covers >95% of real networks). No external lookup at scan time.

**Future history note:** Schema deliberately allows adding a `host_history`
table later (append on each scan_count increment) without breaking current
design. Deferred pending community input on desired retention behaviour.

### `services` Table Update

Add `host_id` FK for direct host→service queries without joining through
discovery history:
```sql
ALTER TABLE services ADD COLUMN host_id INTEGER REFERENCES hosts(id);
```

A `host_current_services` view provides the latest state per host without
scanning historical discovery records.

### Incremental Targeted Rescans

When `monvisor scan <env> --host <ip>` is run:
- Use known probe method from `responds_*` profile (try known-working first,
  short-circuit on first hit, always try all if none recorded).
- Upsert into `hosts` and `services` (latest state only).
- If host does not respond: surface the missing-host prompt (see Inventory
  Ownership Model above).

### New `monvisor hosts` Command

```
monvisor hosts <env>               # all known hosts
monvisor hosts <env> --unknown     # device_type = unknown
monvisor hosts <env> --unmonitored # scan_status = pending
monvisor hosts <env> --missing     # scan_status = missing
monvisor hosts <env> --json        # machine-readable
```

### New Files (4.9)

```
monvisor/cli/scan.py        ← rewritten: two-pass, capability detection
monvisor/cli/hosts.py       ← new monvisor hosts command
monvisor/net/discover.py    ← Pass 1: ICMP/ARP/mDNS host discovery
monvisor/net/fingerprint.py ← Pass 2: service fingerprinting (moved from scan.py)
monvisor/net/oui.py         ← MAC → vendor lookup
monvisor/data/oui_mini.json ← trimmed OUI table (~40KB)
```

### New Optional Dependencies (4.9)

```toml
[project.optional-dependencies]
scan = ["scapy>=2.5"]   # ARP sweep (root required); graceful fallback if absent
```

---

## Phase 4.10 — Brownfield Import

### `monvisor import` Command

```
monvisor import --prometheus-config /path/to/prometheus.yml
               [--alertmanager-config /path/to/alertmanager.yml]
               [--grafana-url http://grafana:3000 --grafana-token <token>]
               [--env <name>]    # default: 'imported'
```

**What it does:**
- Parses prometheus.yml: extracts scrape_configs, static_configs, targets
- Creates environment in SQLite from the job names and targets found
- Populates `hosts` table (scan_status = 'configured' — already in production)
- Populates `services` table from job/target/label data
- Flags targets it cannot resolve (no hostname, dynamic SD targets, etc.)
- Reports what was imported and what needs manual review

**What it does NOT do:**
- Modify the original file
- Trigger a network scan
- Make any assumptions about what "should" be monitored beyond what's in the file

**Partial import handling:**
```
Import complete. Results:
  ✓  23 targets imported from 8 scrape jobs
  ⚠   4 targets flagged for review (no hostname resolvable)
  ✗   2 targets skipped (Kubernetes SD — not yet supported)

Run 'monvisor hosts imported --unmonitored' to review flagged targets.
```

### New Files (4.10)

```
monvisor/cli/import_config.py   ← prometheus.yml / alertmanager.yml parser
monvisor/parsers/prometheus.py  ← scrape_config extraction logic
monvisor/parsers/alertmanager.py
```

---

## Phase 4.11 — Phased Cutover + Alert Suppression

### Alert Suppression Architecture

MonVisor's Alertmanager ships with this default configuration:

```yaml
route:
  receiver: 'null'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'null'   # alerts fire, nothing goes out
```

This is never auto-modified. External receivers are added only by explicit
user command (`monvisor alerting enable ...`).

### Phase Tracking

```yaml
# config.yml
cutover_phase: 1    # 1-4, never auto-advanced
cutover_notes: ""   # user-visible notes on current phase
```

The MonVisor UI and CLI surface the current phase, what it means, and what
the user should do next. Commands for each phase transition:

```
monvisor cutover status           # show current phase + what it means
monvisor cutover advance          # confirm readiness and move to next phase
monvisor alerting enable <type>   # enable a notification channel
monvisor alerting disable <type>  # suppress a channel
monvisor alerting test <type>     # send a test notification
```

### New Files (4.11)

```
monvisor/cli/cutover.py     ← phase tracking, status, advance
monvisor/cli/alerting.py    ← enable/disable/test notification channels
```

---

## Phase 4.12 — IaC Export (Free Tier)

### Purpose

Disaster recovery and reproducibility. If the MonVisor box burns down, the
user can rebuild to known-good state quickly. MonVisor knows everything it
has configured and can emit it as Infrastructure as Code.

### Supported Formats

**Ansible** (primary): Playbooks that reproduce the full MonVisor host state.
**Terraform** (secondary): Modules for users who provision the host via Terraform.
**Puppet / Salt**: Stub commands that print "not yet implemented — contributions welcome."

### What Gets Exported

- Prometheus config, rules, scrape jobs
- Alertmanager config (with suppression state)
- Grafana datasources and dashboards
- Synthetic test definitions and runner service
- MonVisor installation and configuration
- nginx config

### Sync Behaviour

IaC artifacts regenerate automatically whenever the user accepts a
MonVisor-proposed change. Stored in `~/.monvisor/iac/`. The user is
responsible for committing to their own git repository.

```
monvisor iac generate --format ansible    # generate/regenerate
monvisor iac generate --format terraform
monvisor iac status                       # show last generated, any pending changes
monvisor iac diff                         # what would regenerate if run now
```

### New Files (4.12)

```
monvisor/iac/
├── ansible.py      ← playbook generator
├── terraform.py    ← module generator
└── base.py         ← shared rendering logic
monvisor/cli/iac.py ← monvisor iac commands
```

---

## Updated RAG Architecture

```
ChromaDB collections (3):
  'pairs'      ← 231 static pairs — bundled, shipped with MonVisor
  'exemplars'  ← 51 chunks / 14 annotated configs — bundled, shipped
  'learned'    ← dynamic; web-fetched + user content; TTL-managed; NOT shipped

Query routing (ask) — three-tier:
  query → 'pairs' + 'exemplars' + 'learned' (if non-empty)
        → tier 1: RAG hit
        → tier 2: general domain LLM
        → tier 3: web fetch / guided search

Query routing (generate) — unchanged:
  uses 'pairs' + 'exemplars' only
  'learned' NOT injected into generate (keeps YAML output deterministic)
```

---

## Phase Summary

| Phase | Name | Primary Deliverable |
|---|---|---|
| 4.7 | AI Intelligence | 3-tier ask, web fetch, `learned` collection |
| 4.8a | Interactive Configure | `monvisor configure` agent loop |
| 4.8b | Synthetic Monitoring | In-house test runner + exporter |
| 4.9 | Discovery Overhaul | Two-pass scan, `hosts` table, inventory model |
| 4.10 | Brownfield Import | `monvisor import` from existing prometheus.yml |
| 4.11 | Phased Cutover | Alert suppression, phase tracking, safe transition |
| 4.12 | IaC Export | Ansible + Terraform DR artifacts (free tier) |

**Recommended build order: 4.9 → 4.10 → 4.7 → 4.8a → 4.8b → 4.11 → 4.12**

4.9 and 4.10 establish the inventory foundation everything else builds on.
4.7 improves the AI layer that 4.8a/4.8b depend on.
4.11 and 4.12 are complete-the-platform features, buildable independently.

---

## What This Does Not Change

- GPL-3.0 license on this repo.
- Phase 5 (paid features) — still deferred until free tier is solid.
- Ollama / Gemma4 as the LLM runtime.
- RAG `generate` path — unchanged.
- Auth, FastAPI web UI — untouched by these phases.
- Knowledge package format — `learned` is runtime only, never shipped.
