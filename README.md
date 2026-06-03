# MonVisor

**AI-augmented monitoring configuration for Prometheus, Alertmanager, and Grafana.**

MonVisor scans a network, fingerprints the services it finds, lets you approve
what to monitor, and generates Prometheus/Alertmanager/rules YAML — using a
local RAG knowledge base and a local Ollama model. Everything runs locally; no
data leaves the host and there is no API cost.

> Status: free-tier CLI is functional (discovery → review → generate → reports,
> plus an optional web review UI and nginx config). Deploy/Grafana automation is
> the paid tier and not yet implemented.
>
> **Latest release:** [v0.1.1](https://github.com/linuxrebel/MonVisor/releases/tag/v0.1.1) · [all releases](https://github.com/linuxrebel/MonVisor/releases)

## How it works

```
scan  ──▶  review  ──▶  generate  ──▶  (deploy: paid)
 │           │             │
 nmap     yes/no per     RAG + Ollama draft rules.yml;
 + HTTP   service        deterministic prometheus.yml
 probe
```

## Requirements

- Python 3.11+
- [nmap](https://nmap.org/) on `PATH` (service discovery)
- `curl` and `zstd` (needed to install Ollama)
- [Ollama](https://ollama.com/) running locally, with:
  - an LLM (default `gemma4:latest`)
  - the embedding model `nomic-embed-text:latest`
- ~20 GB free disk to install (~16–17 GB used; 35–40 GB total recommended for working room)
- `promtool` (optional) for config validation

Tested on Fedora/RHEL/CentOS/Rocky (dnf) and Debian/Ubuntu (apt). The bundled
installer handles the per-distro differences automatically; see the manual
steps below if you prefer to install by hand.

## Install

**Latest release: [v0.1.1](https://github.com/linuxrebel/MonVisor/releases/tag/v0.1.1)** —
download `monvisor-0.1.1-install.tar.gz` from the
[releases page](https://github.com/linuxrebel/MonVisor/releases), then:

```bash
tar xzf monvisor-0.1.1-install.tar.gz
cd monvisor-0.1.1-install
python3 install.py
```

The tarball bundles the installer, the wheel, this guide, and the license — no
clone or further downloads needed. The rest of this section covers installing
from a clone or by hand.

The fastest path is the bundled installer. It checks and installs the system
prerequisites (nmap, curl, zstd, python venv), installs and starts Ollama and
pulls the models, creates a virtualenv, installs MonVisor, and runs first-time
setup — all in one go:

```bash
python3 scripts/install.py
```

It installs MonVisor from the published GitHub release wheel when available. If
there is no release yet (or you're working from a clone), build the wheel first
so the installer has something local to fall back to:

```bash
pip install build           # one-time, if not already present
python3 -m build            # creates dist/monvisor-*.whl
python3 scripts/install.py  # finds and installs the local dist/ wheel
```

Flags: `--no-sudo` (skip system packages), `--no-models` (skip pulling Ollama
models), `--no-init` (install only), `--install-ollama` / `--no-install-ollama`
(control the Ollama install prompt), `--venv PATH`, `--wheel PATH`.

To do everything by hand instead, follow the four steps below. For a fuller
walkthrough (every prerequisite, plus troubleshooting), see [INSTALL.md](INSTALL.md).

MonVisor is a Python package. The full install is three parts: system tools,
a running Ollama with two models, then the package itself.

### 1. System prerequisites

```bash
# Fedora / RHEL / CentOS / Rocky
sudo dnf install python3 python3-pip nmap curl zstd

# Debian / Ubuntu
sudo apt install python3 python3-pip python3-venv nmap curl zstd
```

`nmap` must be on your `PATH` (scanning depends on it). `curl` and `zstd` are
needed to install Ollama in the next step — the Ollama installer is
zstd-compressed and fails without it. Python 3.11+ is required.

> **Debian/Ubuntu note:** `python3-venv` is a metapackage that can lag the
> installed interpreter on minimal images, leaving `venv` unable to bootstrap
> pip ("ensurepip is not available"). If `python3 -m venv` fails, install the
> version-specific package instead — e.g. `sudo apt install python3.14-venv`
> (match the number to `python3 --version`). The bundled installer does this
> for you automatically.

### 2. Ollama + models (required before `monvisor init`)

`init`, `ask`, and `generate` all use a local Ollama instance, and `init`
builds embeddings from the bundled knowledge, so the models must be pulled
*before* you initialize.

```bash
# install Ollama: https://ollama.com/download  (or: curl -fsSL https://ollama.com/install.sh | sh)
ollama serve &                 # start the server if it isn't already running

ollama pull gemma4             # the LLM (default model)
ollama pull nomic-embed-text   # the embedding model — REQUIRED, init fails without it
```

Ollama listens on `http://localhost:11434` by default. Point MonVisor elsewhere
with `MONVISOR_OLLAMA_URL` or `monvisor config set ollama-url <url>`.

### 3. Install MonVisor

Use a virtual environment to keep dependencies isolated:

```bash
python3 -m venv ~/.venvs/monvisor
source ~/.venvs/monvisor/bin/activate

# from a release wheel (recommended)
pip install monvisor-0.1.1-py3-none-any.whl

# or from the sdist
pip install monvisor-0.1.1.tar.gz

# or from a source clone
pip install .

# or editable, for development
pip install -e .
```

This installs the `monvisor` command. The knowledge base (RAG corpus + reference
configs) ships *inside* the package, so there is nothing else to download —
`monvisor init` is fully self-contained. (Developers can override the corpus
with `MONVISOR_CORPUS` / `MONVISOR_EXEMPLARS`.)

### 4. Initialize

```bash
monvisor init
```

This creates `~/.monvisor/` (database, vector store, reports, configs), loads
the bundled knowledge into the RAG store (embedding takes a minute), and sets a
password for the web UI. Re-running `init` cleanly reloads the knowledge;
`monvisor init --reset-knowledge` forces a fresh rebuild.

Verify it worked:

```bash
monvisor knowledge status       # should report 231 pairs loaded
monvisor ask "How do I run a scan?"
```

To leave the activated environment, run `deactivate` (or just close the
terminal).

To run `monvisor` from any shell without activating the venv each time, add an
alias to `~/.bashrc` (or `~/.zshrc`):

```bash
alias monvisor="$HOME/.venvs/monvisor/bin/monvisor"
```

This is preferable to auto-activating the venv on login, which would also change
which `python`/`pip` the rest of your shell uses. See [INSTALL.md](INSTALL.md)
for details.

## Quick start

After `monvisor init` (see Install above):

```bash
monvisor env add prod 192.168.1.0/24   # register a network as 'prod'
monvisor scan prod                     # discover + fingerprint services
monvisor review prod                   # approve services to monitor (y/b/n/s/a/q)
monvisor generate prod                 # build prometheus.yml + rules.yml
monvisor ui prod                       # optional web review UI (localhost:7373)
monvisor nginx prod                    # optional reverse-proxy config
```

Outputs are written under `~/.monvisor/` (`reports/`, `configs/`).

## Asking the AI

MonVisor has a built-in assistant that answers from its local knowledge base —
both how to use MonVisor and Prometheus/Alertmanager/Grafana questions:

```bash
monvisor ask "How do I run a scan?"
monvisor ask "show me a node_exporter scrape config"
monvisor ask "How do I report a bug?"
```

Answers come only from the bundled knowledge (no internet). If a question isn't
covered, MonVisor says so and points you to the issue tracker rather than
guessing. Add `--show-sources` to see which knowledge snippets were used.

## Configuration

| Env var               | Purpose                                   | Default                  |
|-----------------------|-------------------------------------------|--------------------------|
| `MONVISOR_HOME`       | Data directory                            | `~/.monvisor`            |
| `MONVISOR_OLLAMA_URL` | Ollama endpoint                           | `http://localhost:11434` |
| `MONVISOR_PORT`       | Web UI port                               | `7373`                   |
| `MONVISOR_CORPUS`     | Override RAG corpus path (dev)            | bundled                  |
| `MONVISOR_EXEMPLARS`  | Override exemplar dir (dev)               | bundled                  |

## Tiers

**Free (CLI):** CIDR scan + fingerprinting, terminal + HTML reports, web review UI,
Prometheus/Alertmanager/rules generation, blackbox fallback for un-instrumentable
hosts, exporter recommendations, RAG knowledge updates.

**Professional (planned):** SSH config deploy, Grafana dashboard provisioning,
AI-generated dashboards, Grafana-native review UI, enterprise auth (LDAP, Duo,
AWS IAM, SAML).

## Development

```bash
pip install -e .
python -m build        # build sdist + wheel into dist/
```

## License

MonVisor (the application) is licensed under the GNU General Public License
v3.0 or later (GPL-3.0-or-later) — see [LICENSE](LICENSE).

The bundled knowledge base (`monvisor/knowledge/`) comes from the separate
[MonVisor-Corpus](https://github.com/linuxrebel/MonVisor-Corpus) project and is
licensed CC BY-SA 4.0. The two licenses apply to their respective parts.
