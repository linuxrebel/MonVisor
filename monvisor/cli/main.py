"""
monvisor/cli/main.py
CLI entry point — Click command group and all top-level commands.
"""

import sys
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="monvisor")
def cli():
    """MonVisor — AI-powered monitoring advisor for Prometheus/Grafana.

    \b
    TYPICAL WORKFLOW
      monvisor init                          First-run setup (one time)
      monvisor env add prod 192.168.1.0/24   Register a network as 'prod'
      monvisor scan prod                     Discover + fingerprint services
      monvisor review prod                   Approve services to monitor
      monvisor generate prod                 Build Prometheus/rules/alert YAML
      monvisor deploy prod                   Push configs to the server (paid)

    \b
    SETUP
      init                       Create data dirs, load RAG knowledge, set password
      config set <key> <value>   Store a setting (e.g. grafana-url, ollama-url)
      config get <key>           Read a setting

    \b
    ENVIRONMENTS (named CIDR groups)
      env add <name> <cidr>          Create environment with an initial CIDR
      env add-cidr <name> <cidr>     Add another CIDR to an environment
      env list                       Show environments, CIDRs, and URLs

    \b
    DISCOVERY
      scan <env>                 Scan all CIDRs, fingerprint services, write report
      scan <env> --host <t>      Re-scan specific target(s): IP, range
                                 (192.168.87.36-40), or CIDR. Repeatable.
      scan <env> --new-only      Only record hosts/ports not seen before
      scan <env> --no-html       Terminal report only, skip HTML file

    \b
    REVIEW & GENERATE
      review <env>               Terminal yes/no review per service
      ui <env>                   Launch web review UI (FastAPI)
      generate <env>             RAG + Ollama → prometheus/rules/alert YAML

    \b
    ASK
      ask "<question>"           Ask the AI about MonVisor or monitoring,
                                 answered from the local knowledge base

    \b
    DEPLOY (paid tier)
      deploy <env>               SSH push + promtool validate + reload    [Phase 5]

    \b
    REVERSE PROXY
      nginx [env]                Generate nginx config (Grafana + UI), offer to write

    \b
    KNOWLEDGE BASE
      knowledge status           Show RAG store counts (pairs / exemplars)
      knowledge update <pkg>     Install a knowledge package (tar.gz)

    \b
    DATA & ENV VARS
      Data dir:  ~/.monvisor/   (state.db, chroma/, reports/, configs/)
      MONVISOR_HOME, MONVISOR_OLLAMA_URL, MONVISOR_PORT, MONVISOR_TIER

    Run 'monvisor <command> --help' for details on any command.
    """
    pass


# ── Init ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--reset-knowledge", is_flag=True,
              help="Force a clean reload of the knowledge base (drops any existing store).")
def init(reset_knowledge):
    """First-run setup: create data directories, load knowledge base, set password."""
    from monvisor.config import (ensure_dirs, MONVISOR_HOME, DB_PATH,
                                  CORPUS_SOURCE, EXEMPLARS_SOURCE)
    from monvisor.db.schema import init_db
    from monvisor.rag.ingest import ingest_corpus, ingest_exemplars
    from monvisor.rag.query import verify_rag
    from monvisor.auth.simple import SimpleAuthProvider

    console.print(Panel("[bold blue]MonVisor[/bold blue] — Initializing", expand=False))

    # 1. Create directories
    console.print("  Creating data directories...")
    ensure_dirs()
    console.print(f"  [green]✓[/green] Data directory: {MONVISOR_HOME}")

    # 2. Initialize database
    console.print("  Initializing database...")
    init_db()
    console.print(f"  [green]✓[/green] Database: {DB_PATH}")

    # 3. Check Ollama connectivity
    console.print("  Checking Ollama...")
    try:
        import ollama
        from monvisor.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL
        client = ollama.Client(host=OLLAMA_URL)
        raw = client.list()
        # Handle both dict-style and object-style responses across ollama versions
        model_entries = raw.get("models", raw) if isinstance(raw, dict) else raw.models
        models = []
        for m in model_entries:
            if hasattr(m, "model"):
                models.append(m.model)
            elif hasattr(m, "name"):
                models.append(m.name)
            elif isinstance(m, dict):
                models.append(m.get("model", m.get("name", "")))
        llm_ok   = any(OLLAMA_MODEL.split(":")[0] in m for m in models)
        embed_ok = any(OLLAMA_EMBED_MODEL.split(":")[0] in m for m in models)
        if llm_ok:
            console.print(f"  [green]✓[/green] LLM model: {OLLAMA_MODEL}")
        else:
            console.print(f"  [yellow]⚠[/yellow]  {OLLAMA_MODEL} not found. Run: ollama pull {OLLAMA_MODEL}")
        if embed_ok:
            console.print(f"  [green]✓[/green] Embedding model: {OLLAMA_EMBED_MODEL}")
        else:
            console.print(f"  [yellow]⚠[/yellow]  {OLLAMA_EMBED_MODEL} not found. Run: ollama pull {OLLAMA_EMBED_MODEL}")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow]  Ollama not reachable ({e}). Start Ollama and re-run init.")

    # 4. Load knowledge base
    console.print("  Loading knowledge base into RAG store...")
    # Reset existing collections before ingest so a re-run (or a different
    # bundled corpus) replaces the store cleanly instead of layering new docs
    # on top of orphaned ones. A first run has nothing to reset, so this is safe.
    existing = verify_rag()
    do_replace = reset_knowledge or existing["pairs"] > 0 or existing["exemplars"] > 0
    if do_replace and (existing["pairs"] or existing["exemplars"]):
        console.print(
            f"  [dim]Existing store ({existing['pairs']} pairs, "
            f"{existing['exemplars']} exemplars) will be replaced.[/dim]"
        )
    knowledge_ok = False
    try:
        if not CORPUS_SOURCE.exists():
            console.print(f"  [yellow]⚠[/yellow]  Corpus not found at {CORPUS_SOURCE}")
        else:
            n_pairs = ingest_corpus(replace=do_replace)
            console.print(f"  [green]✓[/green] Ingested {n_pairs} corpus pairs")

        if not EXEMPLARS_SOURCE.exists():
            console.print(f"  [yellow]⚠[/yellow]  Exemplars not found at {EXEMPLARS_SOURCE}")
        else:
            n_exemplars = ingest_exemplars(replace=do_replace)
            console.print(f"  [green]✓[/green] Ingested {n_exemplars} exemplar configs")

        counts = verify_rag()
        console.print(f"  [green]✓[/green] RAG store: {counts['pairs']} pairs, {counts['exemplars']} exemplars")
        knowledge_ok = counts["pairs"] > 0
    except Exception as e:
        console.print(f"  [red]✗[/red]  RAG ingest failed: {e}")
        from monvisor.config import OLLAMA_EMBED_MODEL as _embed
        console.print(
            "  [yellow]This usually means Ollama isn't running or the embedding "
            f"model is missing.[/yellow]\n"
            f"  [dim]Start Ollama, run 'ollama pull {_embed}', "
            "then 'monvisor init --reset-knowledge'.[/dim]"
        )

    # 5. Set password
    console.print()
    if SimpleAuthProvider.is_configured():
        if not Confirm.ask("  Password already set. Reset it?", default=False):
            console.print("  [dim]Password unchanged.[/dim]")
        else:
            _set_password()
    else:
        _set_password()

    # 6. Done
    console.print()
    if knowledge_ok:
        console.print(Panel(
            "[bold green]MonVisor initialized successfully.[/bold green]\n\n"
            "Next steps:\n"
            "  monvisor env add prod 192.168.1.0/24\n"
            "  monvisor scan prod\n"
            "  monvisor review prod\n"
            "  monvisor generate prod\n"
            "  monvisor nginx         (optional: reverse-proxy config)",
            title="Ready", expand=False
        ))
    else:
        from monvisor.config import OLLAMA_EMBED_MODEL as _embed
        console.print(Panel(
            "[bold yellow]MonVisor set up, but the knowledge base is empty.[/bold yellow]\n\n"
            "Directories, database, and password are ready, but no knowledge was\n"
            "loaded — so 'monvisor ask' and 'generate' won't work yet. This means\n"
            "Ollama wasn't reachable or the embedding model wasn't pulled.\n\n"
            "Finish setup once Ollama is running:\n"
            f"  ollama pull {_embed}\n"
            "  monvisor init --reset-knowledge",
            title="Incomplete", expand=False
        ))
        sys.exit(1)


def _set_password():
    from monvisor.auth.simple import SimpleAuthProvider
    while True:
        pw = Prompt.ask("  Set admin password", password=True)
        pw2 = Prompt.ask("  Confirm password", password=True)
        if pw == pw2 and len(pw) >= 8:
            SimpleAuthProvider.set_password(pw)
            console.print("  [green]✓[/green] Password set")
            break
        elif pw != pw2:
            console.print("  [red]Passwords do not match. Try again.[/red]")
        else:
            console.print("  [red]Password must be at least 8 characters.[/red]")


# ── Env commands ──────────────────────────────────────────────────────────────

@cli.group()
def env():
    """Manage named environments (CIDR groups)."""
    pass


@env.command("add")
@click.argument("name")
@click.argument("cidr")
@click.option("--prometheus-url", default=None, help="Prometheus URL for this environment")
@click.option("--grafana-url", default=None, help="Grafana URL for this environment")
def env_add(name, cidr, prometheus_url, grafana_url):
    """Create a new named environment with an initial CIDR."""
    from monvisor.db import queries
    from monvisor.db.schema import init_db
    init_db()

    existing = queries.get_environment(name)
    if existing:
        # Environment exists — just add the CIDR
        queries.add_cidr(existing["id"], cidr)
        console.print(f"[green]✓[/green] Added CIDR {cidr} to existing environment '{name}'")
    else:
        env_id = queries.create_environment(name, prometheus_url, grafana_url)
        queries.add_cidr(env_id, cidr)
        console.print(f"[green]✓[/green] Created environment '{name}' with CIDR {cidr}")


@env.command("add-cidr")
@click.argument("name")
@click.argument("cidr")
@click.option("--label", default=None, help="Optional label for this CIDR")
def env_add_cidr(name, cidr, label):
    """Add an additional CIDR to an existing environment."""
    from monvisor.db import queries
    existing = queries.get_environment(name)
    if not existing:
        console.print(f"[red]Environment '{name}' not found. Create it first:[/red]")
        console.print(f"  monvisor env add {name} {cidr}")
        sys.exit(1)
    queries.add_cidr(existing["id"], cidr, label)
    console.print(f"[green]✓[/green] Added CIDR {cidr} to environment '{name}'")


@env.command("list")
def env_list():
    """List all environments and their CIDRs."""
    from monvisor.db import queries
    from rich.table import Table

    envs = queries.list_environments()
    if not envs:
        console.print("[dim]No environments configured. Run: monvisor env add <name> <cidr>[/dim]")
        return

    table = Table(title="Environments", show_header=True, header_style="bold blue")
    table.add_column("Name", style="bold")
    table.add_column("CIDRs")
    table.add_column("Prometheus URL")
    table.add_column("Grafana URL")
    table.add_column("Created")

    for e in envs:
        cidrs = queries.get_cidrs(e["id"])
        cidr_str = "\n".join(c["cidr"] for c in cidrs) or "[dim]none[/dim]"
        table.add_row(
            e["name"],
            cidr_str,
            e["prometheus_url"] or "[dim]not set[/dim]",
            e["grafana_url"] or "[dim]not set[/dim]",
            e["created_at"][:10],
        )

    console.print(table)


# ── Config command ────────────────────────────────────────────────────────────

@cli.group("config")
def config_cmd():
    """Get and set MonVisor configuration values."""
    pass


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a configuration value (e.g. grafana-url, ollama-url)."""
    from monvisor.db import queries
    queries.set_setting(key, value)
    console.print(f"[green]✓[/green] Set {key} = {value}")


@config_cmd.command("get")
@click.argument("key")
def config_get(key):
    """Get a configuration value."""
    from monvisor.db import queries
    val = queries.get_setting(key)
    if val:
        console.print(f"{key} = {val}")
    else:
        console.print(f"[dim]{key} not set[/dim]")


# ── Placeholder commands (implemented in later phases) ────────────────────────

@cli.command()
@click.argument("environment")
@click.option("--new-only", is_flag=True, help="Only scan hosts not previously discovered")
@click.option("--host", "hosts", multiple=True, metavar="TARGET",
              help="Re-scan specific target(s) instead of the full CIDR: a single IP "
                   "(192.168.87.36), an nmap range (192.168.87.36-40), or a CIDR. Repeatable.")
@click.option("--no-html", is_flag=True, help="Skip HTML report generation")
def scan(environment, new_only, hosts, no_html):
    """Scan an environment's CIDRs and fingerprint services.

    Use --host to target specific machines, e.g. after installing an exporter:
      monvisor scan prod --host 192.168.87.36
      monvisor scan prod --host 192.168.87.36-40   (nmap range)
      monvisor scan prod --host 192.168.87.36 --host 192.168.87.40
    """
    from monvisor.cli.scan import run_scan
    from monvisor.cli.report import terminal_report, html_report
    from monvisor.db import queries

    summary = run_scan(environment, new_only=new_only, hosts=list(hosts) or None)
    if summary is None:
        sys.exit(1)

    services = queries.get_services(summary["env_id"])
    terminal_report(environment, services)

    if not no_html and services:
        path = html_report(environment, services)
        console.print(f"  [green]✓[/green] HTML report: {path}")

    if summary["services"] == 0:
        if summary.get("targeted"):
            console.print("  [dim]No services found on the targeted host(s).[/dim]")
        else:
            console.print("  [dim]No services discovered this run.[/dim]")


@cli.command()
@click.argument("environment")
def review(environment):
    """Interactively review discovered services for monitoring."""
    from monvisor.cli.review import run_review
    run_review(environment)


@cli.command()
@click.argument("environment")
def generate(environment):
    """Generate Prometheus/Alertmanager/Rules YAML configs via RAG."""
    from monvisor.cli.generate import run_generate
    run_generate(environment)


@cli.command()
@click.argument("environment")
def deploy(environment):
    """Deploy generated configs to the Prometheus server via SSH. [Phase 5]"""
    console.print("[yellow]deploy command coming in Phase 5 (paid tier)[/yellow]")


@cli.command()
@click.argument("environment", required=False)
@click.option("--port", default=None, type=int, help="Override web UI port")
def ui(environment, port):
    """Launch the MonVisor web review UI."""
    import os
    import uvicorn
    from monvisor.config import WEB_HOST, WEB_PORT
    from monvisor.api.server import create_app

    listen_port = port or WEB_PORT

    # Detect headless/remote session → print SSH tunnel guidance.
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        host = os.uname().nodename
        console.print(Panel(
            f"No local display detected (remote session).\n\n"
            f"From your workstation, open an SSH tunnel:\n"
            f"  [bold]ssh -L {listen_port}:localhost:{listen_port} {os.environ.get('USER','user')}@{host}[/bold]\n\n"
            f"Then browse to:  [bold]http://localhost:{listen_port}/[/bold]",
            title="Remote access", expand=False,
        ))

    target = f"  http://{WEB_HOST}:{listen_port}/"
    if environment:
        target = f"  http://{WEB_HOST}:{listen_port}/env/{environment}"
    console.print(f"[green]✓[/green] MonVisor UI on {WEB_HOST}:{listen_port}")
    console.print(target)

    uvicorn.run(create_app(), host=WEB_HOST, port=listen_port, log_level="warning")


@cli.group()
def knowledge():
    """Manage RAG knowledge packages."""
    pass


@knowledge.command("status")
def knowledge_status():
    """Show current knowledge base status."""
    from monvisor.rag.query import verify_rag
    try:
        counts = verify_rag()
        console.print(f"[green]✓[/green] Pairs:     {counts['pairs']}")
        console.print(f"[green]✓[/green] Exemplars: {counts['exemplars']}")
    except Exception as e:
        console.print(f"[red]RAG store error: {e}[/red]")
        console.print("[dim]Run: monvisor init[/dim]")


@knowledge.command("update")
@click.argument("package_path")
def knowledge_update(package_path):
    """Install a MonVisor knowledge update package (tar.gz)."""
    from monvisor.cli.update import run_knowledge_update
    run_knowledge_update(package_path)


@cli.command()
@click.argument("environment", required=False)
@click.option("--print-only", is_flag=True, help="Print the config without offering to write it")
def nginx(environment, print_only):
    """Generate the nginx reverse-proxy config (Grafana + MonVisor UI)."""
    from monvisor.cli.nginx import emit_nginx_config
    emit_nginx_config(environment, offer_write=not print_only)


# ── Ask (RAG Q&A) ───────────────────────────────────────────────────────────

# Distance above which the nearest knowledge is considered unrelated. Calibrated
# against nomic-embed-text cosine distances: in-domain questions land ~0.17-0.30,
# clearly out-of-domain ~0.46+. A model-side sentinel is the authoritative gate;
# this is just a cheap pre-filter to skip the LLM call on obvious misses.
_ASK_MAX_DISTANCE = 0.40
_ASK_FALLBACK = (
    "I've not yet learned how to do that.\n\n"
    "If this is something MonVisor should know, please file it so it can be added:\n"
    "  https://github.com/linuxrebel/MonVisor/issues"
)


@cli.command()
@click.argument("question")
@click.option("--show-sources", is_flag=True, help="Also print the knowledge snippets used.")
def ask(question, show_sources):
    """Ask the MonVisor AI a question, answered from its local knowledge base.

    \b
    Examples:
      monvisor ask "How do I run a scan?"
      monvisor ask "show me a node_exporter scrape config"

    Answers come only from MonVisor's local knowledge (no internet). If the
    knowledge base doesn't cover the question, MonVisor says so and points you
    to the issue tracker rather than guessing.
    """
    from monvisor import config
    from monvisor.rag.query import retrieve, build_context

    # Layer 1 — cheap distance pre-filter. If nothing retrieved, or the nearest
    # match is clearly unrelated, don't even call the model.
    try:
        hits = retrieve(question, "pairs", n_results=1)
    except Exception as e:
        console.print(f"[red]Knowledge base unavailable:[/red] {e}")
        console.print("Have you run [bold]monvisor init[/bold] yet?")
        sys.exit(1)

    if not hits or hits[0]["distance"] > _ASK_MAX_DISTANCE:
        console.print(_ASK_FALLBACK)
        return

    # Layer 2 — retrieve full context and let the model judge sufficiency.
    context = build_context(question, n_pairs=4, n_exemplars=2)
    prompt = (
        "You are MonVisor's built-in assistant. Answer the user's question using "
        "ONLY the knowledge provided below. Do not use outside knowledge or guess.\n"
        "If the knowledge below does not actually answer the question, reply with "
        "exactly this token and nothing else: INSUFFICIENT_CONTEXT\n\n"
        f"=== KNOWLEDGE ===\n{context}\n=== END KNOWLEDGE ===\n\n"
        f"Question: {question}\n\nAnswer:"
    )

    try:
        import ollama
        client = ollama.Client(host=config.OLLAMA_URL)
        resp = client.chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = (resp["message"]["content"] if isinstance(resp, dict)
                  else resp.message.content).strip()
    except Exception as e:
        console.print(f"[red]Could not reach the local model:[/red] {e}")
        console.print(f"Check that Ollama is running at {config.OLLAMA_URL}.")
        sys.exit(1)

    if "INSUFFICIENT_CONTEXT" in answer or not answer:
        console.print(_ASK_FALLBACK)
        return

    console.print(answer)

    if show_sources:
        console.print("\n[dim]── sources ──[/dim]")
        for h in retrieve(question, "pairs", n_results=4):
            instr = h["metadata"].get("instruction", "")[:80]
            console.print(f"[dim]• ({h['distance']:.2f}) {instr}[/dim]")


if __name__ == "__main__":
    cli()
