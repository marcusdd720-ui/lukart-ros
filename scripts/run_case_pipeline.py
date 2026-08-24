"""Case pipeline – thin CLI over the local CaseSpec registry."""

from __future__ import annotations

import argparse

from knowledge.models.case_registry import get_spec, registered_keys
from knowledge.models.case_workspace import STAGES


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local case workspace pipeline")
    parser.add_argument(
        "--case",
        required=True,
        help="Case key registered by the local application layer",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List locally registered case keys and exit",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help=f"Run single stage only: {', '.join(STAGES)}",
    )
    parser.add_argument(
        "--list-stages",
        action="store_true",
        help="List available stages and exit",
    )
    args = parser.parse_args()

    if args.list:
        print("Registered cases:")
        for key in registered_keys():
            print(f"  - {key}")
        return 0

    if args.list_stages:
        print("Stages:")
        for name in STAGES:
            print(f"  - {name}")
        return 0

    try:
        spec = get_spec(args.case)
    except KeyError as exc:
        print(exc)
        return 2

    ws = spec.open()
    kwargs = spec.run_kwargs()
    if args.stage:
        kwargs["stage"] = args.stage
    return ws.run(**kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
