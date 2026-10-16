"""Secret-free hosted Linux proof: real Bubblewrap child, broker, scope receipt.

This is a synthetic test, never production admission or a live provider call.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from core.night_shift import child_process_bridge as bridge_module
from core.night_shift.child_process_bridge import ChildLaunchPlan
from core.night_shift.groq_builder_integration import (
    _required_isolated_bwrap_prefix,
    run_scoped_builder,
)
from core.night_shift.groq_builder_scope import ApprovedBuilderScope
from core.night_shift.groq_local_broker import GroqBrokerPolicy
from core.night_shift.journal import DurableEventJournal
from core.night_shift.leases import LeaseStore

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux-only kernel proof")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, timeout=15,
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": os.devnull},
    )
    return result.stdout.strip()


def test_hosted_real_scoped_builder_bridge_and_receipt(monkeypatch: pytest.MonkeyPatch):
    """Real, unprivileged bwrap subprocess; only provider HTTPS response is synthetic."""
    if os.environ.get("ROS_REQUIRE_HOSTED_BUILDER_PILOT") != "1":
        pytest.skip("hosted bwrap pilot only runs in its gated CI stage")
    bwrap = shutil.which("bwrap")
    if not bwrap:
        pytest.fail("required Bubblewrap binary missing", pytrace=False)
    with tempfile.TemporaryDirectory(prefix="ros-hosted-pilot-", dir="/var/tmp") as temp:
        root = Path(temp)
        root.chmod(0o755)
        primary = root / "host-git"
        primary.mkdir()
        worker = root / "worker"
        _git("init", "-q", str(primary))
        (primary / "baseline.txt").write_text("baseline\n", encoding="utf-8")
        _git("-C", str(primary), "add", "baseline.txt")
        _git("-C", str(primary), "-c", "user.name=Synthetic Pilot",
             "-c", "user.email=synthetic.invalid", "commit", "-qm", "baseline")
        _git("-C", str(primary), "worktree", "add", "-q", "-b",
             "night-shift/hosted-pilot", str(worker))
        sha = _git("-C", str(worker), "rev-parse", "HEAD")
        assert (worker / ".git").is_file()

        private = root / "private-broker"
        private.mkdir(mode=0o700)
        broker_socket = private / "broker.sock"
        task_id = "ROS-PR363-HOSTED-BOUNDED-PILOT"
        marker = "ROS_PR363_HOSTED_SYNTHETIC_PROVIDER"
        policy = GroqBrokerPolicy(task_id=task_id, task_marker=marker, max_requests=1)
        scope = ApprovedBuilderScope(
            task_id=task_id, worktree=worker, branch="night-shift/hosted-pilot",
            base_sha=sha, allowed_files=("generated.py",), max_files=1,
        )
        db = root / "journal.db"
        leases = LeaseStore(db)
        journal = DurableEventJournal(db)
        lease = leases.acquire(
            task_id=task_id, lease_id="hosted-pilot-lease",
            worker_id="hosted-pilot-child", now_epoch=int(time.time()), ttl_seconds=45,
        )

        # The isolated child can access ONLY the mounted Unix socket, not network.
        script = (
            "import json, socket, time\n"
            "from pathlib import Path\n"
            "marker = 'ROS_PR363_HOSTED_SYNTHETIC_PROVIDER'\n"
            "body = json.dumps({'model':'openai/gpt-oss-120b','stream':False,"
            "'messages':[{'role':'user','content':marker}]}).encode()\n"
            "request = (b'POST /openai/v1/chat/completions HTTP/1.0\\r\\n'"
            " + b'Host: local\\r\\nContent-Length: ' + str(len(body)).encode()"
            " + b'\\r\\n\\r\\n' + body)\n"
            "with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:\n"
            "    peer.settimeout(5)\n"
            "    peer.connect('/run/lukart-groq.sock')\n"
            "    peer.sendall(request)\n"
            "    response = bytearray()\n"
            "    while chunk := peer.recv(4096):\n"
            "        response.extend(chunk)\n"
            "assert bytes(response).startswith(b'HTTP/1.0 200'), 'broker denied'\n"
            "Path('/workspace/generated.py').write_text('SYNTHETIC = True\\n')\n"
            "progress = Path('/workspace/.night-shift-progress')\n"
            "progress.write_text('start')\n"
            "time.sleep(0.45)\n"
            "progress.write_text('complete')\n"
            "time.sleep(0.45)\n"
            "progress.unlink()\n"
        )
        executable = Path(bwrap).resolve(strict=True)
        argv = _required_isolated_bwrap_prefix(scope, broker_socket) + (
            "/usr/bin/python3", "-c", script,
        )
        plan = ChildLaunchPlan(
            task_id=task_id, worker_id=lease.worker_id, lease_id=lease.lease_id,
            fencing_token=lease.fencing_token, role="BUILDER", executable=executable,
            executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            arguments=argv, worktree=worker, base_sha=sha,
            heartbeat_seconds=0.1, no_progress_seconds=3.0, timeout_seconds=12.0,
            lease_ttl_seconds=45,
        )

        class MockResponse:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __init__(self):
                self.stream = io.BytesIO(
                    b'{"choices":[{"message":{"content":"synthetic"}}]}'
                )

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read1(self, n):
                return self.stream.read(n)

        outbound_count = []

        def mock_outbound(_opener, request, *, timeout):
            assert request.full_url == "https://api.groq.com/openai/v1/chat/completions"
            assert timeout <= 55
            outbound_count.append(json.loads(request.data))
            return MockResponse()

        # No real credentials; only a fake key and a local synthetic HTTPS response.
        monkeypatch.setattr(
            "core.night_shift.groq_builder_integration.read_groq_key",
            lambda _path: "gsk_" + "S" * 32,
        )
        monkeypatch.setattr("urllib.request.OpenerDirector.open", mock_outbound)
        # Synthetic-only stderr capture: diagnose the real bwrap child exit.
        # The production bridge keeps stderr redirected to /dev/null.
        child_stderr = root / "synthetic-child.stderr"
        original_popen = subprocess.Popen

        def record_synthetic_child_stderr(*args, **kwargs):
            executable_fd = kwargs.get("executable", "")
            if isinstance(executable_fd, str) and executable_fd.startswith(
                "/proc/self/fd/"
            ):
                assert kwargs["stderr"] == subprocess.DEVNULL
                descriptor = os.open(
                    child_stderr, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                try:
                    return original_popen(*args, **{**kwargs, "stderr": descriptor})
                finally:
                    os.close(descriptor)
            return original_popen(*args, **kwargs)

        monkeypatch.setattr(
            bridge_module.subprocess, "Popen", record_synthetic_child_stderr
        )
        try:
            result = run_scoped_builder(
                leases=leases, journal=journal, plan=plan, scope=scope,
                broker_policy=policy, auth_file=root / "never-read",
                broker_socket=broker_socket,
                pinned_launch_arguments_sha256=hashlib.sha256(
                    "\0".join(argv).encode()
                ).hexdigest(),
                trusted_admission_checker=lambda _plan: True,  # synthetic fixture only
            )
        except Exception as exc:
            # Only this synthetic worker is inspected; never print real prompts/keys.
            diagnostic = (
                child_stderr.read_bytes()[:4096].decode("utf-8", "replace")
                if child_stderr.exists() else "<no child stderr>"
            )
            raise AssertionError(
                f"synthetic hosted builder failed: {exc}; stderr={diagnostic!r}"
            ) from exc
        events = journal.verify_chain(workflow_id=f"child-bridge:{task_id}")
        kinds = [e.event_type for e in events]
        assert "CHILD_LAUNCH_INTENT" in kinds
        assert "CHILD_STARTED" in kinds
        assert "CHILD_PROGRESS" in kinds
        assert "CHILD_EXIT" in kinds
        assert kinds[-1] == "BUILDER_SCOPE_RECEIPT"
        assert result.process_pid > 0
        assert result.broker_attempts == 1 and len(outbound_count) == 1
        assert (worker / "generated.py").read_text() == "SYNTHETIC = True\n"
        assert result.modified_file_digests == {
            "generated.py": hashlib.sha256(b"SYNTHETIC = True\n").hexdigest(),
        }
        assert not (worker / ".night-shift-progress").exists()
        assert not broker_socket.exists()
        assert events[-1].payload["acceptance"] == "SCOPE_ONLY_NOT_CODE_REVIEW"
        print("ROS_HOSTED_SYNTHETIC_REAL_BUILDER_PROOF_PASS=true", flush=True)
