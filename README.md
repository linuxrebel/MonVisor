# MonVisor

**AI-augmented monitoring configuration for Prometheus, Alertmanager, and Grafana.**

MonVisor scans a network, fingerprints the services it finds, lets you approve
what to monitor, and generates Prometheus/Alertmanager/rules YAML — using a
local RAG knowledge base and a local Ollama model. Everything runs locally; no
data leaves the host and there is no API cost.

> Status: free-tier CLI is functional (discovery → review → generate → reports,
> plus an optional web review UI and nginx config). Deploy/Grafana automation is
> the paid tier and not yet implemented.

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
- [nmap](https://nmap.org/) on `PATH` (`sudo dnf install nmap`)
- [Ollama](https://ollama.com/) running locally, with:
  - an LLM (default `gemma4:latest`)
  - the embedding model `nomic-embed-text:latest`
- `promtool` (optional) for config validation

## Install

```bash
# from a clone
pip install .

# or editable, for development
pip install -e .
```

The knowledge base (RAG corpus + reference configs) ships inside the package,
so `monvisor init` is self-contained. Developers can point at an external corpus
with `MONVISOR_CORPUS` / `MONVISOR_EXEMPLARS`.

## Quick start

```bash
monvisor init                          # create ~/.monvisor, load knowledge, set password
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

MIT — see [LICENSE](LICENSE).
