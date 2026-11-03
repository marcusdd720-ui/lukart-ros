# Accepted ROS task to Persistent Outbox integration

Scope: isolated synthetic integration; no production enablement or CASE data.
Baseline: PR #379 head 5f727f7bc6248d6810800f57ec87f46fb6319aeb.
Current main was verified as 3d73da2c85748f3f10771247e0e47d1f2a2fa4c5.

## Evidence and decision

Earlier producer discovery inspected a stale checkout without core/night_shift.
The live repository has TaskCapsule, authorize_task, AuthorityBudgetStore and
DurableEventJournal. It still lacked an accepted-task creation function connecting
those contracts to outbox delivery. CASE history and transient AgentTask are not
used as task authorities.

Alternatives:
1. Enqueue after in-memory creation: rejected; process death loses the task/event.
2. Add another task database: rejected; creates competing authority.
3. Refactor journal append plus legacy outbox into a shared transaction: stronger
   coupling, incompatible stores and larger schema changes.
4. Chosen: persist an authorized immutable TaskCapsule in the existing journal,
   then replay accepted events through the existing outbox unique key.

The journal's committed TASK_ACCEPTED_V1 is the task acceptance boundary.
Admission requires fresh state, bound policy, allowed risk/repository and a real
durable envelope reservation through the existing authorize_task gate.
This gate does not grant promotion, identity, real-case or production authority.
The synthetic runner's envelope is explicitly HUMAN for promotion.

The reconciler verifies complete per-workflow hash chains and original admission
authority before any enqueue. No volatile callback/watermark is authoritative.
After a commit-to-enqueue crash, rerun reconciliation. After an ambiguous enqueue,
rerun reconciliation. Both produce the same outbox event key. Replay is bounded
and fails closed when its explicit limit is exceeded; it does not silently skip
new work. It uses original acceptance time to validate persisted admission, not
to authorize a fresh execution after expiry. Consumers retain their own gates.

The existing sender now accepts an explicit board argument (default unchanged),
so native CLI checks can use an isolated board without switching the owner board.
A transport DELIVERED state means Kanban accepted the notice; it is not worker
completion. Worker ACK must independently bind the native task identity,
idempotency key, actual subprocess result and completed run.

## Isolated integration commands

Use the existing Python environment with this checkout on sys.path.

python -m scripts.integrations.ros_outbox_synthetic --directory PATH --step accept --task-id synthetic_outbox_e2e_20261103_002
python -m scripts.integrations.ros_outbox_synthetic --directory PATH --step reconcile
python -m scripts.integrations.ros_outbox_synthetic --directory PATH --step deliver --hermes-cli PATH_TO_EXISTING_HERMES

The CLI runner admits only a bounded synthetic hashing task; no model calls,
case materials, paid API credentials or code execution from task text are used.
The dedicated native worker is validation/native_hermes_canary_worker.py.

Rollback: stop invoking this isolated intake/reconciler. Existing owner services,
scheduled jobs, live databases and ordinary producer paths are unchanged.
Do not delete journal/evidence data as rollback; the accepted event is retained.


Review fixes before final immutable candidate:
- Worker refuses Python optimized mode before imports; native ownership/source checks remain active.
- New execution requires exact accepted Git HEAD, branch, repository identity and clean checkout.
- Canary is explicitly external synthetic fixture input, not proof of generic repository-path execution authority.
- ACK verifies native completed run metadata plus the actual native task idempotency key via read-only SQLite.
- Interrupted acceptance can reconstruct canary/manifest from the committed event without creating a fresh state/envelope.
- The synthetic runner supports --fault-after-source-commit (exit91) to prove that recovery boundary in a real child process.
- Worker leg is an external deterministic subprocess using native Hermes claim/complete, NOT a model-driven Hermes agent.
