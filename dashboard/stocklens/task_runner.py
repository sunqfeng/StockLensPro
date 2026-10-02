import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path


def _write_status(status_path, updates):
    status = {}
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status = {}

    status.update(updates)
    status_path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Run a StockLens manual task.")
    parser.add_argument("--status-path", required=True)
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--stderr-path", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    status_path = Path(args.status_path)
    stdout_path = Path(args.stdout_path)
    stderr_path = Path(args.stderr_path)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)

    _write_status(
        status_path,
        {
            "status": "RUNNING",
            "runner_started_at": datetime.now().isoformat(timespec="seconds"),
        },
    )

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
    ) as stderr_file:
        try:
            result = subprocess.run(
                command,
                cwd=args.cwd,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                check=False,
            )
            status = "SUCCESS" if result.returncode == 0 else "FAILED"
            return_code = result.returncode
        except Exception as exc:
            stderr_file.write(f"\n[runner error] {exc}\n")
            status = "FAILED"
            return_code = -1

    _write_status(
        status_path,
        {
            "status": status,
            "return_code": return_code,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


if __name__ == "__main__":
    main()
