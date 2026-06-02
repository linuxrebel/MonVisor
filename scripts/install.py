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
import time
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

OLLAMA_INSTALL_CMD = "curl -fsSL https://ollama.com/install.sh | sh"


def confirm(prompt, default_yes=True):
    """Interactive y/n. Non-interactive (no TTY) returns the default."""
    if not sys.stdin.isatty():
        return default_yes
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        ans = input(f"{prompt} {suffix} ").strip().lower()
    except EOFError:
        return default_yes
    if not ans:
        return default_yes
    return ans in ("y", "yes")


def install_ollama(mode):
    """mode: 'prompt' | 'yes' | 'no'. Returns True if Ollama is available after."""
    if have("ollama"):
        return True
    if mode == "no":
        warn("  Ollama not installed and --no-install-ollama set. Install it yourself:")
        warn(f"    {OLLAMA_INSTALL_CMD}")
        return False

    warn("  Ollama is not installed. It is required for embeddings and answers.")
    warn(f"  This will run, as root via sudo where needed:  {OLLAMA_INSTALL_CMD}")
    if mode == "prompt" and not confirm("  Install Ollama now?", default_yes=True):
        warn("  Skipping Ollama install. Install it yourself, then re-run:")
        warn(f"    {OLLAMA_INSTALL_CMD}")
        return False

    say("  Installing Ollama (downloads and runs the official install script)...")
    # Pipe the official installer through a shell. This is the upstream-blessed
    # method; we surface the exact command above and gate it behind consent.
    r = subprocess.run(OLLAMA_INSTALL_CMD, shell=True)
    if r.returncode != 0 or not have("ollama"):
        warn("  Ollama install did not complete. Install it manually and re-run.")
        return False
    say("  Ollama installed.")
    return True


def start_ollama():
    """Ensure the Ollama server is responding on :11434. Returns True if up."""
    if ollama_running():
        return True
    # Prefer a managed service if the installer set one up.
    if have("systemctl"):
        subprocess.run(["sudo", "systemctl", "enable", "--now", "ollama"],
                       capture_output=True)
        if _wait_for_ollama(10):
            return True
    # Fall back to a detached background server.
    say("  Starting 'ollama serve' in the background...")
    try:
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        warn(f"  Could not start Ollama: {e}")
        return False
    return _wait_for_ollama(15)


def _wait_for_ollama(seconds):
    for _ in range(seconds):
        if ollama_running():
            return True
        time.sleep(1)
    return False


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


def ensure_models(skip_models, ollama_mode):
    """Install Ollama (per mode), start it, and pull models.
    Returns True if both models are present and Ollama is reachable."""
    say("Checking Ollama and models...")

    if not install_ollama(ollama_mode):
        return False  # message already printed

    if not start_ollama():
        warn("  Ollama is installed but not responding on localhost:11434.")
        warn("  Start it ('ollama serve &' or 'sudo systemctl start ollama'), then:")
        warn(f"    ollama pull {EMBED_MODEL} && ollama pull {LLM_MODEL}")
        warn("    monvisor init --reset-knowledge")
        return False

    if skip_models:
        warn("  --no-models set; skipping model pulls. These are required for init:")
        warn(f"    {LLM_MODEL}, {EMBED_MODEL}")
        return False

    ok = True
    for model in (EMBED_MODEL, LLM_MODEL):  # embed first — init needs it most
        if ollama_has(model):
            say(f"  {model} already present.")
            continue
        say(f"  Pulling {model} (this can be several GB)...")
        r = run(["ollama", "pull", model])
        if r.returncode != 0:
            warn(f"  Failed to pull {model}.")
            ok = False
    return ok and ollama_has(EMBED_MODEL)


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
    ap.add_argument("--install-ollama", action="store_true",
                    help="install Ollama without prompting if missing")
    ap.add_argument("--no-install-ollama", action="store_true",
                    help="never install Ollama; only check for it")
    args = ap.parse_args()

    if sys.version_info < (3, 11):
        die(f"Python 3.11+ required (have {sys.version.split()[0]}).")

    ollama_mode = "prompt"
    if args.install_ollama:
        ollama_mode = "yes"
    elif args.no_install_ollama:
        ollama_mode = "no"

    print(f"\n{C_OK}MonVisor installer{C_END}  (v{VERSION})\n")

    ensure_system_packages(args.no_sudo)
    models_ready = ensure_models(args.no_models, ollama_mode)

    venv_path = Path(args.venv).expanduser()
    wheel = resolve_wheel(args.wheel, venv_path.parent if venv_path.parent.exists()
                          else Path.cwd())
    venv_path.parent.mkdir(parents=True, exist_ok=True)
    monvisor_bin = install_into_venv(venv_path, wheel)

    if not monvisor_bin.exists():
        die("Install finished but the 'monvisor' command was not found in the venv.")
    say(f"Installed: {monvisor_bin}")

    # init needs Ollama + the embedding model to build the knowledge store.
    # Don't run it (and produce an empty store) if we know that isn't ready.
    init_ran = False
    if args.no_init:
        say("Skipping init (--no-init).")
    elif not models_ready:
        warn("Skipping 'monvisor init': Ollama / embedding model not ready.")
        warn("Once Ollama is running with the models pulled, finish setup with:")
        warn(f"    ollama pull {EMBED_MODEL} && ollama pull {LLM_MODEL}")
        warn(f"    {monvisor_bin} init --reset-knowledge")
    else:
        say("Running first-time setup (monvisor init)...")
        print()
        run([str(monvisor_bin), "init"])
        init_ran = True

    # Post-init verification: confirm the knowledge actually loaded.
    init_ok = None
    if init_ran:
        try:
            out = subprocess.run([str(monvisor_bin), "knowledge", "status"],
                                 capture_output=True, text=True, timeout=30).stdout
            digits = [int(s) for s in out.replace(":", " ").split() if s.isdigit()]
            pairs = digits[0] if digits else 0
            init_ok = pairs > 0
            if init_ok:
                say(f"Verified knowledge base: {pairs} pairs loaded.")
            else:
                warn("Knowledge base is EMPTY after init (0 pairs).")
                warn("Ollama or the embedding model was not reachable during ingest. Fix with:")
                warn(f"    ollama pull {EMBED_MODEL}")
                warn(f"    {monvisor_bin} init --reset-knowledge")
        except Exception as e:
            warn(f"Could not verify knowledge status: {e}")

    activate = venv_path / "bin" / "activate"
    if init_ran and init_ok:
        print(f"\n{C_OK}Done — MonVisor is ready.{C_END}")
    else:
        print(f"\n{C_WARN}Install finished, but setup is incomplete (see warnings above).{C_END}")
    print(f"  Activate the environment:  {C_DIM}source {activate}{C_END}")
    print(f"  Then try:                  {C_DIM}monvisor ask \"How do I run a scan?\"{C_END}")
    print(f"  Or run directly:           {C_DIM}{monvisor_bin} --help{C_END}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("Interrupted.")
