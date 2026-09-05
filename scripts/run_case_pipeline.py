"""Run a dynamically discovered private local MVROS case workspace."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.models.case_registry import get_spec, registered_keys
from knowledge.models.case_workspace import STAGES, CaseWorkspace

_RELEASE_STAGES = frozenset({"OUTBOUND", "RELEASE"})


def _configure_release_boundary(
    workspace: CaseWorkspace,
    stage: str | None,
    kwargs: dict[str, Any],
) -> None:
    """Keep local case analysis non-publishing until a cognitive chain is bound."""

    if stage is None:
        kwargs["sync_outbound"] = False
        return

    if stage.strip().upper() in _RELEASE_STAGES:
        workspace.cognitive_release_enforced = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a case workspace from the private local store"
    )
    parser.add_argument("--case", required=False, help="Private local case key")
    parser.add_argument("--data-root", default=None, help="Private local MVROS data root")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List local/registered case keys and exit",
    )
    parser.add_argument(
        "--stage", default=None, help=f"Run single stage only: {', '.join(STAGES)}"
    )
    parser.add_argument(
        "--list-stages", action="store_true", help="List available stages and exit"
    )
    args = parser.parse_args()

    data_root = Path(args.data_root).expanduser() if args.data_root else None
    if data_root:
        os.environ["MVROS_DATA_ROOT"] = str(data_root)

    if args.list:
        print("Available local/registered case keys:")
        for key in registered_keys(data_root=data_root):
            print(f"  - {key}")
        return 0

    if args.list_stages:
        print("Stages:")
        for name in STAGES:
            print(f"  - {name}")
        return 0

    if not args.case:
        print("ERROR: --case is required for a real local case")
        return 2

    try:
        spec = get_spec(args.case, data_root=data_root)
    except (KeyError, ValueError, RuntimeError) as exc:
        print(exc)
        return 2

    ws = spec.open(data_root=data_root)
    kwargs = spec.run_kwargs()
    _configure_release_boundary(ws, args.stage, kwargs)
    if args.stage:
        kwargs["stage"] = args.stage
    return ws.run(**kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
