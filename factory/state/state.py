import json
from datetime import datetime
from pathlib import Path


class StateManager:
    """Zarządza stanem projektu (LOCKED / ACTIVE)."""

    STATE_FILE = "rqm_state.json"

    def __init__(self, root: Path):
        self.state_file = root / self.STATE_FILE
        self.state: dict = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}

    def save_state(self, files, changes, health):
        self.state["last_run"] = datetime.now().isoformat()
        self.state["health_score"] = health.score
        self.state_file.write_text(
            json.dumps(self.state, indent=2, default=str), encoding="utf-8"
        )

    def get_previous_state(self) -> dict:
        return self.state
