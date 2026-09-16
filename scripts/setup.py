#!/usr/bin/env python3
"""Prepare the local demo; use --vector only for the optional embedding stack."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    executable = shutil.which(args[0])
    if executable is None:
        raise SystemExit(f"Install {args[0]} and try again.")
    subprocess.run([executable, *args[1:]], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vector', action='store_true')
    args = parser.parse_args()
    run('uv', 'sync', '--locked', *(['--extra', 'vector'] if args.vector else []))
    run('npm', '--prefix', 'frontend', 'ci', '--no-fund', '--no-audit')
    run('npm', '--prefix', 'frontend', 'run', 'build')
    if args.vector:
        run('uv', 'run', '--extra', 'vector', 'python', '-c',
            "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')")
    run('uv', 'run', '--locked', 'python', '-m', 'backend.src.cli', 'init')
    print('Setup complete. Run: uv run --locked uvicorn backend.src.api.main:app --host 127.0.0.1 --port 8377')
    return 0


if __name__ == '__main__':
    sys.exit(main())
