"""Check that generated runtime secrets cannot appear in distributable files."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    files = [ROOT / p for p in paths if p and (ROOT / p).is_file()]
    forbidden = [p for p in paths if p == ".env" or p.startswith((".runtime/", ".venv/", "node_modules/")) or p.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm"))]
    if forbidden:
        raise SystemExit("Runtime file included in distributable Git files: " + ", ".join(forbidden))
    env = ROOT / ".env"
    if env.exists():
        secrets = []
        for line in env.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if any(marker in key for marker in ["PASSWORD", "TOKEN", "SECRET_KEYS"]) and len(value) >= 12:
                secrets.append(value.encode())
        for path in files:
            data = path.read_bytes()
            if any(value in data for value in secrets):
                raise SystemExit("A generated secret was found in " + str(path.relative_to(ROOT)))
    print(f"PASS: {len(files)} distributable files; runtime directories and generated secret values excluded")


if __name__ == "__main__":
    main()
