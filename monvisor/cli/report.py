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
monvisor/cli/report.py
Phase 2 — Discovery reporting.

Rich terminal output grouped by host, plus a standalone HTML report written
to ~/.monvisor/reports/.
"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from monvisor import config
from monvisor.recommend import recommendations, EXPORTER_HINT

console = Console()

# Service types MonVisor knows how to monitor (highlighted as actionable).
_MONITORABLE = set(config.FINGERPRINTS.values())


def terminal_report(environment: str, services: list[dict]) -> None:
    """Print a grouped, color-coded discovery report to the terminal."""
    if not services:
        console.print(f"[yellow]No services discovered for '{environment}'.[/yellow]")
        return

    by_host: dict[str, list[dict]] = defaultdict(list)
    for s in services:
        by_host[s["host"]].append(s)

    table = Table(
        title=f"Discovery — {environment}  ({len(services)} services on {len(by_host)} hosts)",
        show_header=True, header_style="bold blue",
    )
    table.add_column("Host", style="bold")
    table.add_column("Port", justify="right")
    table.add_column("Service")
    table.add_column("Version", style="dim")
    table.add_column("Status")

    for host in sorted(by_host):
        rows = sorted(by_host[host], key=lambda r: r["port"])
        for i, s in enumerate(rows):
            decided = s.get("monitor")
            mode = s.get("monitor_mode")
            if decided == 1 and mode == "blackbox":
                status = "[magenta]blackbox[/magenta]"
            elif decided == 1:
                status = "[green]monitor[/green]"
            elif decided == 0:
                status = "[red]skip[/red]"
            else:
                status = "[dim]undecided[/dim]"

            stype = s["service_type"] or "unknown"
            stype_disp = f"[cyan]{stype}[/cyan]" if stype in _MONITORABLE else stype

            table.add_row(
                host if i == 0 else "",
                str(s["port"]),
                stype_disp,
                s.get("version") or "—",
                status,
            )
        table.add_section()

    console.print(table)

    # Exporter recommendations — echo to terminal.
    recs = recommendations(services)
    if recs:
        console.print("\n[bold]Exporter recommendations[/bold] (no metrics endpoint found):")
        for host in sorted(recs):
            for exp in recs[host]:
                hint = EXPORTER_HINT.get(exp, "")
                console.print(f"  [yellow]→[/yellow] {host}: install [cyan]{exp}[/cyan]"
                              + (f" [dim]({hint})[/dim]" if hint else ""))
        console.print("  [dim]If an exporter can't be installed on a host, choose "
                      "'blackbox' during review for remote probing.[/dim]")

    console.print(
        f"\n  Run [bold]monvisor review {environment}[/bold] to approve services for monitoring."
    )


def html_report(environment: str, services: list[dict]) -> Path:
    """Write an HTML discovery report and return its path."""
    config.REPORTS_PATH.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = config.REPORTS_PATH / f"{environment}-{ts}.html"

    by_host: dict[str, list[dict]] = defaultdict(list)
    for s in services:
        by_host[s["host"]].append(s)

    rows_html = []
    for host in sorted(by_host):
        host_rows = sorted(by_host[host], key=lambda r: r["port"])
        span = len(host_rows)
        for i, s in enumerate(host_rows):
            decided = s.get("monitor")
            mode = s.get("monitor_mode")
            if decided == 1 and mode == "blackbox":
                badge = '<span class="b bb">blackbox</span>'
            elif decided == 1:
                badge = '<span class="b monitor">monitor</span>'
            elif decided == 0:
                badge = '<span class="b skip">skip</span>'
            else:
                badge = '<span class="b undecided">undecided</span>'

            stype = html.escape(s["service_type"] or "unknown")
            known = "known" if (s["service_type"] in _MONITORABLE) else ""
            version = html.escape(s.get("version") or "—")

            host_cell = (
                f'<td class="host" rowspan="{span}">{html.escape(host)}</td>'
                if i == 0 else ""
            )
            rows_html.append(
                f"<tr>{host_cell}"
                f'<td class="port">{s["port"]}</td>'
                f'<td class="svc {known}">{stype}</td>'
                f'<td class="ver">{version}</td>'
                f"<td>{badge}</td></tr>"
            )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build the recommendations block.
    recs = recommendations(services)
    if recs:
        rec_rows = []
        for host in sorted(recs):
            items = ", ".join(
                f'<code>{html.escape(e)}</code>'
                + (f' <span class="hint">{html.escape(EXPORTER_HINT.get(e, ""))}</span>'
                   if EXPORTER_HINT.get(e) else "")
                for e in recs[host]
            )
            rec_rows.append(f"<tr><td class='host'>{html.escape(host)}</td><td>{items}</td></tr>")
        rec_html = (
            "<h2>Exporter recommendations</h2>"
            "<p class='note'>Hosts with no Prometheus metrics endpoint. "
            "Install the suggested exporter, or mark the host <em>blackbox</em> "
            "in review for remote probing.</p>"
            "<table class='recs'><thead><tr><th>Host</th><th>Recommended exporters</th>"
            "</tr></thead><tbody>" + "\n".join(rec_rows) + "</tbody></table>"
        )
    else:
        rec_html = ""

    doc = _HTML_TEMPLATE.format(
        env=html.escape(environment),
        generated=generated,
        host_count=len(by_host),
        service_count=len(services),
        rows="\n".join(rows_html),
        recommendations=rec_html,
    )
    out.write_text(doc, encoding="utf-8")
    return out


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MonVisor Discovery — {env}</title>
<style>
  :root {{ --bg:#0f1419; --panel:#1a1f29; --line:#2a3140; --fg:#e6e9ef;
           --muted:#7a869a; --cyan:#39c5cf; --green:#3fb950; --red:#f85149;
           --amber:#d29922; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
          font:14px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif; }}
  header {{ padding:28px 32px; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0; font-size:20px; }}
  h1 span {{ color:var(--cyan); }}
  .meta {{ color:var(--muted); margin-top:6px; font-size:13px; }}
  .wrap {{ padding:24px 32px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--panel);
           border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  th, td {{ padding:10px 14px; text-align:left; border-bottom:1px solid var(--line); }}
  th {{ background:#161b22; color:var(--muted); font-weight:600;
        text-transform:uppercase; font-size:11px; letter-spacing:.04em; }}
  td.host {{ font-weight:600; vertical-align:top; border-right:1px solid var(--line); }}
  td.port {{ font-variant-numeric:tabular-nums; color:var(--muted); }}
  td.svc.known {{ color:var(--cyan); }}
  td.ver {{ color:var(--muted); font-size:13px; }}
  .b {{ font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600; }}
  .b.monitor {{ background:rgba(63,185,80,.15); color:var(--green); }}
  .b.skip {{ background:rgba(248,81,73,.15); color:var(--red); }}
  .b.undecided {{ background:rgba(210,153,34,.15); color:var(--amber); }}
  .b.bb {{ background:rgba(187,128,255,.18); color:#bb80ff; }}
  h2 {{ font-size:15px; margin:28px 0 6px; }}
  .note {{ color:var(--muted); font-size:13px; margin:0 0 12px; }}
  .recs code {{ background:#161b22; color:var(--cyan); padding:1px 6px;
                border-radius:4px; font-size:13px; }}
  .recs .hint {{ color:var(--muted); font-size:12px; }}
  footer {{ padding:18px 32px; color:var(--muted); font-size:12px;
            border-top:1px solid var(--line); }}
</style>
</head>
<body>
<header>
  <h1>MonVisor Discovery — <span>{env}</span></h1>
  <div class="meta">{service_count} services across {host_count} hosts &middot; generated {generated}</div>
</header>
<div class="wrap">
  <table>
    <thead><tr><th>Host</th><th>Port</th><th>Service</th><th>Version</th><th>Status</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>
  {recommendations}
</div>
<footer>Generated by MonVisor &middot; review with <code>monvisor review {env}</code></footer>
</body>
</html>
"""
