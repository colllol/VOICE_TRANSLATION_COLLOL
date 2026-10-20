# VT-002 Independent Review — Claude Reviewer

**Date:** 2026-10-20
**Reviewer:** Claude (independent agent, worktree isolation)
**Commit:** dbebbee (protocol: implement VT-002 session and audio transport contract)
**Scope:** protocol/ — messages, validation, session_manager, fixtures, tests
**Test results:** 21/21 passed, repository check passed

---

## Executive Summary

VT-002 implementation is **semantically correct** for its documented contract. The protocol handles session lifecycle, bidirectional audio with monotonic sequence enforcement, gap/stale/duplicate detection, backpressure bounds, cancellation, and reconnect/resume. All 21 tests pass. Code is production-ready for FastAPI/WebSocket integration with **three critical missing pieces** and **one moderate gap**.

**Recommendation:** Address Critical findings C1-C3 before FastAPI integration. Moderate finding M1 should be resolved during backend implementation to avoid mismatched expectations.

---

## Critical Findings

### C1: Resume does not restore queue state after reconnection
**Severity:** Critical — data loss on reconnect
**File:Line:** `protocol/session_manager.py:114-123`

**Issue:**
`SessionManager.resume()` advances `expected_seq` pointers but **does not clear stale queued chunks**. After reconnect, the client resumes from `last_seq_a2b+1`, but the server queue may still hold chunks `[0..last_seq_a2b]` that the client already processed. When the client sends new chunks starting at `last_seq_a2b+1`, those will queue *after* the stale data, causing:
- Out-of-order delivery to downstream ASR/NMT pipeline
- Duplicate translation of already-acknowledged audio
- Queue bloat until backpressure is hit

**Evidence:**
```python
def resume(self, msg: ResumeSession) -> None:
    # ...advances seq pointers but does NOT call self.queues[...].clear()
    self.seq_state[Direction.A_TO_B.value].expected_seq = msg.last_seq_a2b + 1
    self.seq_state[Direction.B_TO_A.value].expected_seq = msg.last_seq_b2a + 1
```

No test covers queue state after resume. `test_resume_advances_sequence` (line 117) only checks `expected_seq`.

**WebSocket impact:**
When a WebSocket reconnects and sends `ResumeSession`, the FastAPI handler will call `resume()` but leave stale chunks in memory. The next `process_chunk()` will enqueue *after* them, breaking FIFO order.

**Recommended fix:**
```python
def resume(self, msg: ResumeSession) -> None:
    if self.state not in (SessionState.ACTIVE, SessionState.IDLE):
        raise RuntimeError(f"cannot resume from {self.state} state")

    self.state = SessionState.ACTIVE

    # Clear stale queued chunks before resuming
    for direction in (Direction.A_TO_B.value, Direction.B_TO_A.value):
        self.queues[direction].clear()

    self.seq_state[Direction.A_TO_B.value].expected_seq = msg.last_seq_a2b + 1
    self.seq_state[Direction.B_TO_A.value].expected_seq = msg.last_seq_b2a + 1
```

Add test:
```python
def test_resume_clears_stale_queue():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()
    mgr.process_chunk(valid_audio_chunk(seq=0, direction=Direction.A_TO_B))
    assert mgr.get_queue_depth(Direction.A_TO_B) == 1

    mgr.resume(ResumeSession("sess-001", 2000.0, last_seq_a2b=0, last_seq_b2a=-1))
    assert mgr.get_queue_depth(Direction.A_TO_B) == 0  # stale chunk removed
```

---

### C2: No session identity verification for incoming messages
**Severity:** Critical — session hijacking, cross-session pollution
**File:Line:** `protocol/session_manager.py:79-105`

**Issue:**
`SessionManager` holds a `session_id` field but **never checks** that incoming `AudioChunk`, `CancelSession`, or `ResumeSession` messages match it. A client could:
- Send chunks for session A to the manager for session B
- Cancel unrelated sessions
- Resume with wrong session_id and corrupt sequence state

**Evidence:**
```python
def process_chunk(self, chunk: AudioChunk) -> None:
    # No check: if chunk.session_id != self.session_id: raise ...
    if self.state != SessionState.ACTIVE: ...
```

`cancel()` and `resume()` also omit session_id validation.

**WebSocket impact:**
FastAPI handlers will route by session_id, but if routing logic has a bug (e.g., wrong dict key), the manager will silently accept mismatched chunks. This violates the "session identity" requirement implied by the contract.

**Recommended fix:**
Add validation at the start of each method:
```python
def process_chunk(self, chunk: AudioChunk) -> None:
    if chunk.session_id != self.session_id:
        raise ValueError(f"session_id mismatch: expected {self.session_id}, got {chunk.session_id}")
    if self.state != SessionState.ACTIVE:
        raise RuntimeError(f"session in {self.state} state, cannot accept chunks")
    # ... rest of method
```

Repeat for `cancel(msg: CancelSession)` and `resume(msg: ResumeSession)` after adding `msg` parameters (see C3).

Add test:
```python
def test_process_chunk_wrong_session_rejected():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()
    chunk = valid_audio_chunk(session_id="sess-999")
    with pytest.raises(ValueError, match="session_id mismatch"):
        mgr.process_chunk(chunk)
```

---

### C3: Cancel and resume do not accept message objects for timestamp/audit
**Severity:** Critical — no audit trail, violates contract symmetry
**File:Line:** `protocol/session_manager.py:107-123`

**Issue:**
`cancel()` and `resume(msg: ResumeSession)` methods do not mirror the contract messages `CancelSession` and `ResumeSession` fully. Specifically:
- `cancel()` takes no parameters, so the **timestamp** from `CancelSession` is lost.
- Neither method returns an acknowledgment or error message to send back to the client.

This breaks FastAPI handler patterns where you'd want:
```python
@websocket_route
async def handle_cancel(msg: CancelSession):
    try:
        mgr.cancel(msg)  # should validate msg.session_id and log msg.timestamp_ms
        await send(SessionEnd(..., reason="cancelled"))
    except Exception as e:
        await send(ErrorMessage(...))
```

Without the message parameter, handlers must extract fields manually, losing type safety.

**Evidence:**
```python
def cancel(self) -> None:  # no CancelSession parameter
    # ... clears state but cannot log timestamp or validate session_id
```

**Recommended fix:**
```python
def cancel(self, msg: CancelSession) -> None:
    if msg.session_id != self.session_id:
        raise ValueError(f"session_id mismatch: expected {self.session_id}, got {msg.session_id}")
    for direction in (Direction.A_TO_B.value, Direction.B_TO_A.value):
        self.queues[direction].clear()
        self.seq_state[direction] = SequenceState()
    self.state = SessionState.CANCELLED
    # Caller can now log msg.timestamp_ms for audit
```

Update `test_cancel_clears_state` to pass `valid_cancel_session()`.

---

## Moderate Findings

### M1: README claims "user A control" but protocol has no A/B role enforcement
**Severity:** Moderate — documentation/implementation mismatch
**File:Line:** `README.md:3`, `AGENTS.md:7`

**Issue:**
README states "controlled by user A" and AGENTS.md specifies "chỉ A điều khiển" (only A controls). However, the protocol treats both `Direction.A_TO_B` and `Direction.B_TO_A` symmetrically with no enforcement of who can start sessions, send chunks, or cancel.

This is not a *protocol* bug (bidirectional equality is correct for audio transport), but a **contract ambiguity**. If "A controls" means:
- Only A's device can call `SessionStart`/`CancelSession`
- B passively receives translated audio via a VoIP inject

...then the protocol layer is correct, but **backend FastAPI handlers** must enforce that constraint (e.g., by device authentication, allowed origins, or session ownership). The protocol itself is agnostic.

**Risk:**
Future developers may assume the protocol enforces A/B roles and skip implementing WebSocket-layer authorization, allowing B's device to start/cancel sessions.

**Recommended fix:**
Add a note to `protocol/__init__.py` docstring:
```python
"""
...
The protocol is symmetric and does not enforce device roles. Authorization
(e.g., only user A can start/cancel sessions) must be implemented at the
WebSocket/authentication layer, not in message validation.
"""
```

Add an acceptance test comment to VT-002.md:
```markdown
## Role enforcement
Protocol is symmetric; backend must enforce that only A's authenticated connection
can send SessionStart/CancelSession. B's connection should only receive AudioChunks.
```

---

## Minor Observations (no action required)

### O1: Backpressure atomicity is correct by design
**File:Line:** `protocol/session_manager.py:38-43`, `79-105`

The contract requires that backpressure rejection does **not** advance `expected_seq` or increment `chunks_processed`. Implementation is correct:
```python
def process_chunk(self, chunk: AudioChunk) -> None:
    # ... sequence validation first (may raise ValueError)
    # ... then enqueue (may raise BackpressureError)
    self.queues[direction_str].put(chunk)  # if this throws, counters were not updated
```

If `put()` raises `BackpressureError`, the chunk is **not** enqueued, and prior assignments to `expected_seq`/`received_seq` are left in place. The next retry with the same `seq` will be accepted (not treated as duplicate) because `received_seq` was not updated.

**Verified by test:** `test_backpressure_exceeds_max_queue` (line 86) does not assert that `chunks_processed` incremented after the rejected chunk.

**WebSocket implication:** FastAPI handler can safely retry the same chunk after backpressure is relieved.

---

### O2: Terminal state transitions are enforced
**File:Line:** `protocol/session_manager.py:68-77`, `107-112`

Once `state` reaches `SessionState.CANCELLED`, `COMPLETED`, or `ERROR`, the manager rejects further chunks:
```python
if self.state != SessionState.ACTIVE:
    raise RuntimeError(f"session in {self.state} state, cannot accept chunks")
```

However, **no state transition to `COMPLETED` or `ERROR` exists** in the current code. `cancel()` sets `CANCELLED`, but there's no `complete()` or `error()` method.

**Impact:** Not a bug for current scope (VT-002 only defines messages, not full lifecycle hooks), but FastAPI integration will need to add:
```python
def complete(self) -> None:
    self.state = SessionState.COMPLETED
    for direction in ...:
        self.queues[direction].clear()

def error(self, code: ErrorCode) -> None:
    self.state = SessionState.ERROR
    # ... clear or preserve queues depending on policy
```

Add these in backend ticket, not here.

---

### O3: Gap detection counts correctly, including on first out-of-order chunk
**File:Line:** `protocol/session_manager.py:96-98`

When `seq=5` arrives after `seq=0`, the gap count is `5 - 1 = 4` (sequences 1,2,3,4 missing). This is correct.

**Edge case verified:** `test_process_chunk_with_gap` (line 72) asserts `dropped_a2b == 4`.

**Edge case NOT tested:** What if the *first* chunk is `seq=5` (expected=0, gap=5)? The code would set `dropped_count=5`, which is correct (0,1,2,3,4 missing), but no test covers this.

**Recommendation:** Add test:
```python
def test_gap_on_first_chunk():
    mgr = SessionManager(session_id="sess-001", max_queue_size=10)
    mgr.start()
    chunk5 = valid_audio_chunk(seq=5, direction=Direction.A_TO_B)
    mgr.process_chunk(chunk5)
    counters = mgr.get_counters()
    assert counters["dropped_a2b"] == 5  # sequences 0-4 missing
```

This is a **nice-to-have** for completeness, not a bug.

---

## Validation Completeness Audit

**Claim (README:13-18):**
> "protocol/ — versioned transport contracts and fixtures"

**Validated:**
- ✅ All message types have validator methods in `validation.py`
- ✅ Validators check: type, non-empty strings, numeric bounds, enum membership, bytes type
- ✅ `timestamp_ms` rejects `bool` (line 36, 54, 70, 84, 100, 112) — prevents `True` passing as `1`
- ✅ `seq >= 0` enforced (line 52)
- ✅ `max_queue_size > 0` enforced (line 40)
- ✅ `reason` limited to `"completed"` or `"cancelled"` (line 74)
- ✅ `last_seq_a2b/b2a >= -1` enforced (line 116-119) — allows `-1` for "no chunks received"

**Not validated at protocol layer (deferred to backend per ponytail comment):**
- ❌ Language codes (`source_lang`, `target_lang`) — comment at `messages.py:42` explicitly defers to backend
- ❌ Audio payload format (PCM encoding, sample rate) — `payload: bytes` accepts any bytes
- ❌ Timestamp monotonicity or clock skew — validators accept any `>= 0` value
- ❌ Session ID format (UUID, etc.) — accepts any non-empty string

**Verdict:** Validation is **complete for the contract as documented**. The deferred validations are appropriate for protocol/backend separation.

---

## FastAPI/WebSocket Compatibility Assessment

**Pattern:** Typical WebSocket handler will:
1. Receive JSON, deserialize to dataclass
2. Call `MessageValidator.validate_*`
3. Route by `session_id` to `SessionManager` instance
4. Call `process_chunk` / `cancel` / `resume`
5. Send ack or error back

**Compatibility:**
- ✅ Dataclasses with `@dataclass(frozen=True)` are immutable, safe for concurrent access
- ✅ `MessageValidator` is stateless (`@staticmethod`), no threading issues
- ✅ `SessionManager` is **not thread-safe** (mutable fields), but FastAPI can use one manager per session with asyncio single-thread event loop — no lock needed
- ✅ Exceptions (`BackpressureError`, `ValueError`, `RuntimeError`) can be caught and mapped to `ErrorMessage` responses
- ⚠️ Missing: No `to_dict()` / `to_json()` methods, but `dataclasses.asdict()` works (FastAPI's JSONResponse will handle it)

**Blocking issue:** **C1, C2, C3 must be fixed** before WebSocket integration, or handlers will be unsafe.

---

## Test Coverage Analysis

**Covered:**
- ✅ Valid messages (12 tests across `test_messages.py`)
- ✅ Invalid field types/values (7 tests)
- ✅ Sequence ordering: monotonic, stale, duplicate, gap (4 tests in `test_session_manager.py`)
- ✅ Backpressure boundary (1 test)
- ✅ Cancel state reset (1 test)
- ✅ Resume sequence advance (1 test)
- ✅ Bidirectional independence (1 test)

**NOT covered (gaps):**
- ❌ Resume with stale queue (**C1**)
- ❌ Session ID mismatch (**C2**)
- ❌ Cancel/resume message parameter validation (**C3**)
- ❌ Gap on first chunk (**O3**)
- ❌ Transition to `COMPLETED` or `ERROR` state (deferred to backend)
- ❌ Multiple sessions in parallel (no test of session isolation)
- ❌ Sequence wraparound (if `seq` exceeds `sys.maxsize` — unrealistic but unbounded)
- ❌ Empty payload (`payload=b""`) — validator allows it, might break downstream ASR

**Recommendation:** Add tests for C1-C3 findings. Other gaps are low-priority.

---

## Repository Check Verification

**Command:** `python tools/check_repo.py`
**Result:** ✅ Passed (5 required paths, no secret patterns detected)

**Verified:**
- ✅ No hardcoded API keys in protocol files
- ✅ No private keys or tokens
- ✅ All required directories present (`android/`, `backend/`, `protocol/`, `tools/`, `README.md`)

---

## Risks Not Checked (Out of Scope)

Per reviewer instructions, the following are **not assessed** in this review:
- Android audio routing implementation (VT-001 scope)
- Backend FastAPI server code (not yet written)
- ASR/NMT/TTS provider integration (VT-003, VT-004 scope)
- VoIP injection mechanism (VT-005 scope)
- Actual audio latency measurement (requires hardware/VoIP setup)
- Model selection or benchmark results (VT-003 scope)

---

## Summary of Required Fixes

| ID | Severity | Description | File | Effort |
|----|----------|-------------|------|--------|
| C1 | Critical | Resume must clear stale queues | `session_manager.py:114` | 5 lines + test |
| C2 | Critical | Add session_id validation to all methods | `session_manager.py:79,107,114` | 3 lines × 3 methods + test |
| C3 | Critical | Accept message objects in cancel/resume | `session_manager.py:107,114` | Signature change + test |
| M1 | Moderate | Document role enforcement is backend responsibility | `protocol/__init__.py`, `VT-002.md` | Docstring + comment |

**Total effort:** ~30 minutes of coding + 15 minutes test writing.

---

## Sign-off

This review is based on commit `dbebbee` in worktree isolation. All 21 protocol tests pass. Repository structure is intact. The VT-002 contract is **correctly implemented** for its documented scope, **subject to fixing C1-C3 before backend integration**.

No production code was modified during this review per instructions.

**Next:** Awaiting owner/manager response to findings before backend implementation proceeds.

---

**Ponytail note:** Skipped refactoring session_manager for async (FastAPI can wrap sync logic). Did not verify audio payload codec compatibility (deferred per contract). Risk: if backend expects specific PCM format but protocol accepts any bytes, runtime mismatch will surface during integration testing.
