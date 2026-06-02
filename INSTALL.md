# Installing MonVisor from a clone

This guide takes you from `git clone` to a working `monvisor` command. If you
just want the short version, the repository `README.md` has it; this document
is the complete, copy-pasteable walkthrough including every prerequisite.

MonVisor runs entirely on your own host. Nothing is sent to the cloud; the AI
features use a local [Ollama](https://ollama.com/) instance.

## What you need

- A Linux host (Fedora/RHEL, Debian/Ubuntu, or Arch). macOS works for the
  Python parts but the system-package step assumes Linux.
- Python 3.11 or newer.
- About 11 GB of free disk for the Ollama models.
- sudo access (to install system packages and Ollama).

## The two ways to install

1. **Scripted** — `python3 scripts/install.py` does everything below for you.
2. **Manual** — the five steps in "Manual install" if you'd rather run each part
   yourself or the script doesn't fit your environment.

Both produce the same result: MonVisor installed in a virtualenv, Ollama running
with the required models, and a populated knowledge base.

## Scripted install

```bash
git clone https://github.com/linuxrebel/MonVisor.git
cd MonVisor

# The installer downloads the release wheel if one is published. From a clone
# there usually isn't one yet, so build it first — the installer then finds and
# uses the local dist/ wheel automatically.
pip install build
python3 -m build

python3 scripts/install.py
```

The script will, in order:

1. Check and install system prerequisites: `nmap`, `curl`, `zstd`, python venv.
2. Install Ollama if missing (it shows the exact command and asks first), start
   it, and pull `nomic-embed-text` and `gemma4`.
3. Create a virtualenv at `~/.venvs/monvisor` and install MonVisor into it.
4. Run `monvisor init` and verify the knowledge base loaded (231 pairs).

Useful flags:

- `--no-sudo` — don't install system packages (you've handled them).
- `--no-models` — don't pull Ollama models.
- `--install-ollama` / `--no-install-ollama` — decide the Ollama install without
  the interactive prompt (handy for automation).
- `--no-init` — install only; run `monvisor init` yourself later.
- `--venv PATH` — install somewhere other than `~/.venvs/monvisor`.
- `--wheel PATH` — install a specific wheel instead of downloading/searching.

When it finishes it prints how to activate the environment.

## Manual install

Five steps. This is exactly what the script automates.

### 1. System prerequisites

```bash
# Fedora / RHEL
sudo dnf install -y python3 python3-pip nmap curl zstd

# Debian / Ubuntu
sudo apt install -y python3 python3-pip python3-venv nmap curl zstd

# Arch
sudo pacman -S --noconfirm python python-pip nmap curl zstd
```

`nmap` is used for service discovery. `curl` and `zstd` are required to install
Ollama in the next step: the Ollama installer ships zstd-compressed and aborts
with "requires zstd for extraction" if zstd is absent.

### 2. Install and start Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version          # confirm it installed

# start the server (one of these)
sudo systemctl enable --now ollama      # if the installer set up a service
ollama serve &                          # otherwise, run it in the background
```

### 3. Pull the models

```bash
ollama pull nomic-embed-text   # embeddings — REQUIRED, init fails without it
ollama pull gemma4             # the LLM (~9.6 GB)
ollama list                    # both should appear
```

### 4. Install MonVisor into a virtualenv

```bash
python3 -m venv ~/.venvs/monvisor
source ~/.venvs/monvisor/bin/activate

# from a clone: build and install
pip install build
python3 -m build
pip install dist/monvisor-*.whl

# or simply:
pip install .
```

### 5. Initialize

```bash
monvisor init
```

Watch for `✓ Ingested 231 corpus pairs`. `init` creates `~/.monvisor/`
(database, vector store, reports, configs), loads the bundled knowledge, and
sets a web-UI password. If Ollama isn't reachable, init now reports the failure
clearly and exits non-zero instead of pretending it succeeded — fix Ollama and
re-run `monvisor init --reset-knowledge`.

## Verify

```bash
source ~/.venvs/monvisor/bin/activate
monvisor knowledge status      # expect: Pairs 231, Exemplars 14
monvisor ask "how do I run a scan"
```

If `ask` returns a real answer (not "I've not yet learned how to do that"), the
knowledge base is loaded and you're ready. See `README.md` for the scan →
review → generate workflow.

## Troubleshooting

**`ask` says "I've not yet learned how to do that" / `knowledge status` shows 0
pairs.** The knowledge never embedded, almost always because Ollama wasn't
running or `nomic-embed-text` wasn't pulled when `init` ran. Fix and reload:

```bash
ollama list                          # confirm nomic-embed-text is present
ollama pull nomic-embed-text         # if it's missing
monvisor init --reset-knowledge
```

**`ERROR: This version requires zstd for extraction`** when installing Ollama.
Install zstd, then re-run the Ollama install:

```bash
sudo dnf install -y zstd     # or apt/pacman
curl -fsSL https://ollama.com/install.sh | sh
```

**Out of disk during model pull.** The models are large — `gemma4` alone is
~9.6 GB, plus `nomic-embed-text` and the Python dependencies. Budget at least
12–15 GB free. Ollama stores models under `~/.ollama` (or `/usr/share/ollama`
when run as a system service); make sure that filesystem has room. On a VM,
size the disk accordingly before installing. To put models elsewhere, set
`OLLAMA_MODELS=/path/with/space` before pulling.

**`ollama: command not found` after install.** The install didn't complete —
check the output above it (commonly the zstd error). Re-run the Ollama install
once the blocker is resolved.

**`monvisor: command not found`.** The virtualenv isn't active. Run
`source ~/.venvs/monvisor/bin/activate`, or call the binary directly at
`~/.venvs/monvisor/bin/monvisor`.

**`init` can't reach Ollama** even though it's installed. Confirm it's serving:
`curl http://localhost:11434/api/tags` should return JSON. If you started it
with `ollama serve &`, that process must stay running; consider the systemd
service instead.
