"""
Knowledge Operating System (KOS)

File: tests/test_project_loader.py
Version: 1.0
Sprint: F-013

Simple test for ProjectStateLoader.
"""

from knowledge.project_loader import ProjectStateLoader


def main():

    loader = ProjectStateLoader()

    state = loader.load()

    print("=" * 50)
    print("KOS Project State")
    print("=" * 50)

    print(f"Iteration        : {state.iteration}")
    print(f"Active case      : {state.active_case}")
    print(f"Patterns         : {state.validated_patterns}")
    print(f"Hypotheses       : {state.active_hypotheses}")
    print(f"Accepted ADRs    : {state.accepted_adrs}")
    print(f"Next steps       : {state.next_steps}")

    print("=" * 50)


if __name__ == "__main__":
    main()