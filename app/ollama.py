import subprocess
from typing import Optional, List, Dict, Any
import requests
from .config import OLLAMA_MODEL, OLLAMA_HOST


def _detect_ollama_commands() -> List[str]:
    """Detect available Ollama subcommands from `ollama --help` output.

    Returns a list ordered by preference (prefer 'run' when available).
    """
    try:
        proc = subprocess.run(["ollama", "--help"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("'ollama' CLI not found. Install Ollama and ensure it's on PATH.")

    help_out = (proc.stdout or proc.stderr or "").lower()
    cmds: List[str] = []

    if "available commands" in help_out:
        collect = False
        for line in help_out.splitlines():
            line = line.rstrip()
            if "available commands" in line:
                collect = True
                continue
            if collect:
                if not line.strip():
                    break
                # Each line looks like: '  run       Run a model'
                parts = line.strip().split()
                if parts:
                    cmds.append(parts[0])

    # Fallback list if parsing failed
    if not cmds:
        cmds = ["run", "predict", "generate"]

    # Prefer 'run' > 'predict' > 'generate' when present
    preferred = []
    for c in ["run", "predict", "generate"]:
        if c in cmds and c not in preferred:
            preferred.append(c)
    for c in cmds:
        if c not in preferred:
            preferred.append(c)

    print(f"Detected Ollama commands/preference: {preferred}")
    return preferred


# Perform detection once at import time
_AVAILABLE_CMD_PREFERENCE = _detect_ollama_commands()


def _normalize_ollama_host(host: str) -> str:
    host = host.strip()
    if not host:
        return "http://127.0.0.1:11434"
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"http://{host.strip('/')}"


def _ollama_http_generate(prompt: str, model: str, options: Optional[Dict[str, Any]] = None, timeout: int = 60) -> str:
    url = f"{_normalize_ollama_host(OLLAMA_HOST)}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if options:
        payload["options"] = options

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to reach Ollama HTTP API at {url}: {e}")

    if resp.status_code != 200:
        raise RuntimeError(f"Ollama HTTP API error {resp.status_code}: {resp.text}")

    data = resp.json()
    out = (data.get("response") or "").strip()
    if not out:
        raise RuntimeError("Ollama HTTP API returned an empty response.")
    return out


def predict_with_ollama(prompt: str, model_id: Optional[str] = None, options: Optional[Dict[str, Any]] = None, timeout: int = 60) -> str:
    """Call the local Ollama CLI using a best-effort strategy.

    Strategy (for each detected command in order):
      1) Try positional prompt: `ollama <cmd> <model> <prompt>`
      2) Try common prompt flags (e.g., `--prompt`, `--input`, etc.)
      3) Try sending the prompt via stdin to `ollama <cmd> <model>`

    Returns the first non-empty output or raises a RuntimeError with `ollama --help` for diagnostics.
    """
    model = model_id or OLLAMA_MODEL

    # Prefer the HTTP API (supports advanced options) and fall back to CLI on failure.
    try:
        return _ollama_http_generate(prompt, model, options=options, timeout=timeout)
    except Exception:
        # Fall back to CLI below
        pass

    try:
        for cmd in _AVAILABLE_CMD_PREFERENCE:
            # 1) Positional prompt (most recent Ollama run supports this)
            try:
                proc = subprocess.run([
                    "ollama",
                    cmd,
                    model,
                    prompt,
                ], capture_output=True, text=True, timeout=timeout)
            except FileNotFoundError:
                raise RuntimeError("'ollama' CLI not found. Install Ollama and ensure it's on PATH.")
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Ollama {cmd} timed out")

            stderr = (proc.stderr or "").lower()
            out = (proc.stdout or proc.stderr or "").strip()
            if proc.returncode == 0 and out:
                return out

            # If return code indicates unknown command, move to next command
            if proc.returncode != 0 and ("unknown command" in stderr or "not a valid command" in stderr):
                continue

            # 2) Try several flag names commonly used for prompt text
            flags_to_try = ["--prompt", "--input", "--text", "-p"]
            for flag in flags_to_try:
                try:
                    proc = subprocess.run([
                        "ollama",
                        cmd,
                        model,
                        flag,
                        prompt,
                    ], capture_output=True, text=True, timeout=timeout)
                except FileNotFoundError:
                    raise RuntimeError("'ollama' CLI not found. Install Ollama and ensure it's on PATH.")
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"Ollama {cmd} timed out")

                stderr = (proc.stderr or "").lower()
                # If this flag isn't recognized by this command, try the next flag
                if proc.returncode != 0 and ("unknown flag" in stderr or "unknown shorthand flag" in stderr or "flag provided but not defined" in stderr):
                    continue

                out = (proc.stdout or proc.stderr or "").strip()
                if out:
                    return out

            # 3) Try passing the prompt via stdin (some versions accept stdin)
            try:
                proc = subprocess.run([
                    "ollama",
                    cmd,
                    model,
                ], input=prompt, capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"Ollama {cmd} timed out when sending prompt via stdin")

            stderr = (proc.stderr or "").lower()
            if proc.returncode == 0:
                out = (proc.stdout or proc.stderr or "").strip()
                if out:
                    return out
            else:
                # If stderr indicates unknown command, move to next cmd
                if "unknown command" in stderr or "not a valid command" in stderr:
                    continue

        # If we reach here, none of the commands produced usable output
        help_proc = subprocess.run(["ollama", "--help"], capture_output=True, text=True, check=False)
        help_out = (help_proc.stdout or help_proc.stderr or "").strip()
        raise RuntimeError(f"Failed to call Ollama with detected subcommands ({_AVAILABLE_CMD_PREFERENCE}). `ollama --help`:\n{help_out}")
    except Exception:
        # Re-raise to preserve stack when used in FastAPI handler
        raise
