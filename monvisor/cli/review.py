"""
monvisor/cli/review.py
Phase 3 — terminal review workflow.

Walks undecided services and records a monitor yes/no decision per service.
"""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Prompt

from monvisor.db import queries
from monvisor.db.schema import init_db
from monvisor.recommend import EXPORTER_FOR, EXPORTER_HINT

console = Console()


def run_review(environment: str) -> None:
    init_db()
    env = queries.get_environment(environment)
    if not env:
        console.print(f"[red]Environment '{environment}' not found.[/red]")
        return

    undecided = queries.get_services(env["id"], undecided_only=True)
    if not undecided:
        decided = queries.get_services(env["id"])
        if decided:
            console.print(f"[green]All {len(decided)} services already reviewed.[/green]")
            console.print(f"  Re-run review by re-scanning, or run: monvisor generate {environment}")
        else:
            console.print(f"[yellow]No services to review. Run: monvisor scan {environment}[/yellow]")
        return

    console.print(
        f"Reviewing [bold]{len(undecided)}[/bold] services in '{environment}'. "
        "[dim](y=monitor via exporter, b=blackbox/not installable, n=skip, "
        "s=skip for now, a=monitor all rest, q=quit)[/dim]\n"
    )

    auto_yes = False
    for i, s in enumerate(undecided, 1):
        label = f"[bold]{s['host']}:{s['port']}[/bold]  {s['service_type'] or 'unknown'}"
        if s.get("version"):
            label += f" [dim]v{s['version']}[/dim]"

        if auto_yes:
            queries.set_service_decision(s["id"], True, monitor_mode="exporter")
            console.print(f"  [{i}/{len(undecided)}] {label}  [green]monitor[/green]")
            continue

        console.print(f"  [{i}/{len(undecided)}] {label}")

        # Hint when this is a plain service with no exporter on the box.
        exp = EXPORTER_FOR.get(s["service_type"])
        if exp:
            hint = EXPORTER_HINT.get(exp, "")
            console.print(
                f"      [dim]no metrics endpoint — needs [cyan]{exp}[/cyan]"
                + (f" ({hint})" if hint else "")
                + "; pick 'b' if you can't install it.[/dim]"
            )

        choice = Prompt.ask(
            "      monitor?", choices=["y", "b", "n", "s", "a", "q"], default="y", show_choices=True
        )
        if choice == "y":
            queries.set_service_decision(s["id"], True, monitor_mode="exporter")
        elif choice == "b":
            queries.set_service_decision(
                s["id"], True, notes="not installable", monitor_mode="blackbox"
            )
            console.print("      [magenta]blackbox[/magenta] — will be probed remotely.")
        elif choice == "n":
            queries.set_service_decision(s["id"], False)
        elif choice == "s":
            continue
        elif choice == "a":
            auto_yes = True
            queries.set_service_decision(s["id"], True, monitor_mode="exporter")
        elif choice == "q":
            console.print("  [dim]Stopped. Progress saved.[/dim]")
            break

    monitored = queries.get_monitored_services(env["id"])
    console.print(
        f"\n[green]\u2713[/green] {len(monitored)} services marked for monitoring. "
        f"Next: monvisor generate {environment}"
    )
