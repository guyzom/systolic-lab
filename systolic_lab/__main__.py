"""Command line interface. Run from the project directory with python -m."""

import argparse
from dataclasses import fields
import json
from pathlib import Path

from .server import serve
from .simulator import Config, simulate, synthetic


def main():
    parser = argparse.ArgumentParser(description="Educational systolic matrix multiplier")
    commands = parser.add_subparsers(dest="command", required=True)
    web = commands.add_parser("serve", help="open a local browser visualization")
    web.add_argument("--port", type=int, default=8000)
    run = commands.add_parser("simulate", help="multiply and verify against an independent reference")
    run.add_argument("--m", type=int, default=5)
    run.add_argument("--k", type=int, default=7)
    run.add_argument("--n", type=int, default=3)
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--input", type=Path, help='JSON object with "a" and "b" matrices')
    run.add_argument("--trace", action="store_true")
    run.add_argument("--output", type=Path, help="save full JSON result")
    for field in fields(Config):
        run.add_argument("--" + field.name, type=int, default=field.default)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            if not 0 <= args.port <= 65535:
                raise ValueError("port must be in [0, 65535]")
            serve(args.port)
            return
        if args.input:
            data = json.loads(args.input.read_text())
            a, b = data["a"], data["b"]
        else:
            a, b = synthetic(args.m, args.k, args.n, args.seed)
        config = Config(**{f.name: getattr(args, f.name) for f in fields(Config)})
        result = simulate(a, b, config, trace=args.trace)
        result["input_kind"] = "provided JSON" if args.input else "seeded synthetic"
        result["seed"] = None if args.input else args.seed
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"verified": result["verified"], "shape": result["shape"],
                          "metrics": result["metrics"], "result": result["result"]}, indent=2))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
