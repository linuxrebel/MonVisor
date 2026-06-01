"""
monvisor/cli/update.py
Phase 4 — knowledge package installer.

Installs a monvisor-knowledge-*.pkg (tar.gz): validates the manifest, backs up
the current ChromaDB store, ingests the package's corpus + exemplars, copies the
package contents into ~/.monvisor/knowledge/v<version>/, records the version,
and prints the changelog.
"""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console

from monvisor import config
from monvisor.db import queries
from monvisor.db.schema import init_db

console = Console()


def _load_manifest(root: Path) -> Optional[dict]:
    mpath = root / "manifest.json"
    if not mpath.exists():
        console.print("  [red]\u2717[/red] Package missing manifest.json")
        return None
    try:
        return json.loads(mpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        console.print(f"  [red]\u2717[/red] Invalid manifest.json: {e}")
        return None


def _backup_chroma() -> Optional[Path]:
    """Copy the current ChromaDB dir to chroma.bak (best effort)."""
    if not config.CHROMA_PATH.exists():
        return None
    bak = config.CHROMA_PATH.with_suffix(".bak")
    try:
        if bak.exists():
            shutil.rmtree(bak)
        shutil.copytree(config.CHROMA_PATH, bak)
        return bak
    except Exception as e:
        console.print(f"  [yellow]\u26a0[/yellow]  Could not back up vector store: {e}")
        return None


def run_knowledge_update(package_path: str) -> None:
    from monvisor.rag.ingest import ingest_corpus, ingest_exemplars

    init_db()
    pkg = Path(package_path).expanduser()
    if not pkg.exists():
        console.print(f"[red]Package not found: {pkg}[/red]")
        return
    if not tarfile.is_tarfile(pkg):
        console.print(f"[red]Not a valid package (expected tar.gz): {pkg}[/red]")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        with tarfile.open(pkg) as tf:
            # Guard against path traversal in archive members.
            for m in tf.getmembers():
                if m.name.startswith("/") or ".." in Path(m.name).parts:
                    console.print(f"[red]Unsafe path in package: {m.name}[/red]")
                    return
            tf.extractall(tmpdir)

        # Some packages wrap contents in a top-level dir; find the manifest root.
        root = tmpdir
        if not (root / "manifest.json").exists():
            subs = [d for d in tmpdir.iterdir() if d.is_dir()]
            if len(subs) == 1 and (subs[0] / "manifest.json").exists():
                root = subs[0]

        manifest = _load_manifest(root)
        if manifest is None:
            return

        version = str(manifest.get("version", "unknown"))
        min_mv = manifest.get("min_monvisor")
        if min_mv and _version_tuple(min_mv) > _version_tuple("0.1.0"):
            console.print(
                f"  [red]\u2717[/red] Package requires MonVisor >= {min_mv} (have 0.1.0). Upgrade first."
            )
            return

        console.print(f"Installing knowledge package [bold]v{version}[/bold]...")

        bak = _backup_chroma()
        if bak:
            console.print(f"  [green]\u2713[/green] Backed up vector store \u2192 {bak}")

        corpus = root / "corpus.jsonl"
        if corpus.exists():
            n = ingest_corpus(corpus)
            console.print(f"  [green]\u2713[/green] Ingested {n} corpus pairs")
        else:
            console.print("  [dim]No corpus.jsonl in package \u2014 skipping pairs.[/dim]")

        exemplars = root / "exemplars"
        if exemplars.is_dir():
            n = ingest_exemplars(exemplars)
            console.print(f"  [green]\u2713[/green] Ingested {n} exemplar chunks")
        else:
            console.print("  [dim]No exemplars/ in package \u2014 skipping.[/dim]")

        # Copy package payload into the knowledge store for the record.
        dest = config.KNOWLEDGE_PATH / f"v{version}"
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(root, dest)
            console.print(f"  [green]\u2713[/green] Installed payload \u2192 {dest}")
        except Exception as e:
            console.print(f"  [yellow]\u26a0[/yellow]  Could not copy payload: {e}")

        queries.set_setting("knowledge_version", version)

    changelog = manifest.get("changelog", "(no changelog provided)")
    console.print(f"\n[green]\u2713[/green] Knowledge updated to v{version}.")
    console.print(f"  Changelog: {changelog}")


def _version_tuple(v: str) -> tuple:
    """Parse 'x.y.z' into a comparable tuple; non-numeric parts become 0."""
    parts = []
    for p in str(v).split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)
