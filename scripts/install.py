#!/usr/bin/env python3
"""
MonVisor installer.

One command to install MonVisor and everything it needs:
  - system packages (nmap, python venv support) via dnf/apt
  - Ollama models (gemma4:latest + nomic-embed-text:latest)
  - the monvisor package into a dedicated virtualenv
  - first-run `monvisor init`

Usage:
    python3 install.py                 # full install
    python3 install.py --no-sudo       # skip system-package step
    python3 install.py --no-models     # skip pulling Ollama models
    python3 install.py --venv PATH     # custom venv location
    python3 install.py --wheel PATH    # install a specific local wheel

Stdlib only — runs on a fresh box that has just python3.
"""

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "linuxrebel/MonVisor"
VERSION = "0.1.0"
WHEEL_NAME = f"monvisor-{VERSION}-py3-none-any.whl"
RELEASE_URL = f"https://github.com/{REPO}/releases/download/v{VERSION}/{WHEEL_NAME}"
LLM_MODEL = "gemma4:latest"
EMBED_MODEL = "nomic-embed-text:latest"
DEFAULT_VENV = Path.home() / ".venvs" / "monvisor"

C_OK, C_WARN, C_ERR, C_DIM, C_END = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def say(msg):  print(f"{C_OK}::{C_END} {msg}")
def warn(msg): print(f"{C_WARN}!!{C_END} {msg}")
def die(msg):  print(f"{C_ERR}xx{C_END} {msg}"); sys.exit(1)
def run(cmd, **kw):
    print(f"{C_DIM}   $ {' '.join(cmd)}{C_END}")
    return subprocess.run(cmd, **kw)
def have(binary): return shutil.which(binary) is not None


# ── system packages ─────────────────────────────────────────────────────────

def detect_pm():
    """Return (manager, install_args) for the host distro, or (None, None)."""
    if have("dnf"):
        return "dnf", ["sudo", "dnf", "install", "-y"]
    if have("apt"):
        return "apt", ["sudo", "apt", "install", "-y"]
    if have("pacman"):
        return "pacman", ["sudo", "pacman", "-S", "--noconfirm"]
    return None, None


def ensure_system_packages(skip_sudo):
    say("Checking system prerequisites (nmap, python venv)...")
    needed = []
    if not have("nmap"):
        needed.append("nmap")
    # venv: importable on most distros, but Debian/Ubuntu split it into python3-venv
    try:
        import venv  # noqa: F401
    except ImportError:
        needed.append("python3-venv")

    if not needed:
        say("  System prerequisites already present.")
        return

    if skip_sudo:
        warn(f"  Missing: {', '.join(needed)} — install manually (--no-sudo set).")
        return

    pm, install = detect_pm()
    if not pm:
        warn(f"  Could not detect package manager. Install manually: {', '.join(needed)}")
        return

    # Package names differ slightly per distro.
    pkgs = []
    for n in needed:
        if n == "python3-venv" and pm in ("dnf", "pacman"):
            continue  # venv bundled with python3 on Fedora/Arch
        pkgs.append("nmap" if n == "nmap" else n)
    if not pkgs:
        return

    say(f"  Installing via {pm}: {', '.join(pkgs)}")
    r = run(install + pkgs)
    if r.returncode != 0:
        warn(f"  Package install returned {r.returncode}. Continuing — verify {pkgs} yourself.")


# ── ollama + models ─────────────────────────────────────────────────────────

def ollama_running():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3):
            return True
    except Exception:
        return False


def ollama_has(model):
    """True if `model` (or its base name) is already pulled."""
    if not have("ollama"):
        return False
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return False
    base = model.split(":")[0]
    return any(base in line for line in out.splitlines())


def ensure_models(skip_models):
    say("Checking Ollama and models...")
    if not have("ollama"):
        warn("  Ollama is not installed. Install it from https://ollama.com/download,")
        warn("  then re-run, or pull the models yourself before 'monvisor init':")
        warn(f"    ollama pull {LLM_MODEL}")
        warn(f"    ollama pull {EMBED_MODEL}")
        return

    if not ollama_running():
        warn("  Ollama is installed but not responding on localhost:11434.")
        warn("  Start it ('ollama serve &') and re-run, or pull the models manually.")
        return

    if skip_models:
        warn("  --no-models set; skipping model pulls. Ensure these exist before init:")
        warn(f"    {LLM_MODEL}, {EMBED_MODEL}")
        return

    for model in (LLM_MODEL, EMBED_MODEL):
        if ollama_has(model):
            say(f"  {model} already present.")
            continue
        say(f"  Pulling {model} (this can be several GB)...")
        r = run(["ollama", "pull", model])
        if r.returncode != 0:
            warn(f"  Failed to pull {model}. Pull it manually before running init.")


# ── locate the wheel ─────────────────────────────────────────────────────────

def find_local_wheel():
    """Look for a built wheel next to this script's repo (../dist/)."""
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "dist", Path.cwd() / "dist"):
        if cand.is_dir():
            wheels = sorted(cand.glob("monvisor-*-py3-none-any.whl"))
            if wheels:
                return wheels[-1]
    return None


def download_release(dest_dir):
    """Try to download the release wheel from GitHub. Returns path or None."""
    dest = dest_dir / WHEEL_NAME
    say(f"  Downloading {WHEEL_NAME} from GitHub release...")
    try:
        with urllib.request.urlopen(RELEASE_URL, timeout=30) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
        return dest
    except Exception as e:
        warn(f"  Release download failed ({e}).")
        return None


def resolve_wheel(explicit, work_dir):
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            die(f"--wheel path not found: {p}")
        return p
    # Prefer GitHub release; fall back to a locally built wheel.
    dl = download_release(work_dir)
    if dl:
        return dl
    local = find_local_wheel()
    if local:
        say(f"  Falling back to local wheel: {local}")
        return local
    die("No wheel found. Build one with `python -m build`, or pass --wheel PATH, "
        f"or publish the v{VERSION} GitHub release.")


# ── venv install ─────────────────────────────────────────────────────────────

def install_into_venv(venv_path, wheel):
    say(f"Creating virtualenv at {venv_path}...")
    import venv as venv_mod
    venv_mod.EnvBuilder(with_pip=True, clear=False).create(venv_path)
    pip = venv_path / "bin" / "pip"
    say("Installing MonVisor and dependencies (this pulls a fair bit)...")
    r = run([str(pip), "install", "--upgrade", "pip", "--quiet"])
    r = run([str(pip), "install", str(wheel)])
    if r.returncode != 0:
        die("pip install failed — see output above.")
    return venv_path / "bin" / "monvisor"


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Install MonVisor and its prerequisites.")
    ap.add_argument("--venv", default=str(DEFAULT_VENV), help="virtualenv location")
    ap.add_argument("--wheel", help="install a specific local wheel instead of downloading")
    ap.add_argument("--no-sudo", action="store_true", help="skip system-package install")
    ap.add_argument("--no-models", action="store_true", help="skip pulling Ollama models")
    ap.add_argument("--no-init", action="store_true", help="install only; skip 'monvisor init'")
    args = ap.parse_args()

    if sys.version_info < (3, 11):
        die(f"Python 3.11+ required (have {sys.version.split()[0]}).")

    print(f"\n{C_OK}MonVisor installer{C_END}  (v{VERSION})\n")

    ensure_system_packages(args.no_sudo)
    ensure_models(args.no_models)

    venv_path = Path(args.venv).expanduser()
    wheel = resolve_wheel(args.wheel, venv_path.parent if venv_path.parent.exists()
                          else Path.cwd())
    venv_path.parent.mkdir(parents=True, exist_ok=True)
    monvisor_bin = install_into_venv(venv_path, wheel)

    if not monvisor_bin.exists():
        die("Install finished but the 'monvisor' command was not found in the venv.")
    say(f"Installed: {monvisor_bin}")

    if args.no_init:
        say("Skipping init (--no-init).")
    else:
        say("Running first-time setup (monvisor init)...")
        print()
        run([str(monvisor_bin), "init"])

    activate = venv_path / "bin" / "activate"
    print(f"\n{C_OK}Done.{C_END}")
    print(f"  Activate the environment:  {C_DIM}source {activate}{C_END}")
    print(f"  Then try:                  {C_DIM}monvisor ask \"How do I run a scan?\"{C_END}")
    print(f"  Or run directly:           {C_DIM}{monvisor_bin} --help{C_END}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("Interrupted.")
