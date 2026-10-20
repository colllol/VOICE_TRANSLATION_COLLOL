# Protocol boundary

Transport schemas are owned by VT-002. Do not add message fields here without the protocol review gate.

## VT-002 Session and Audio Transport Contract

### Overview

Concrete, dependency-free session lifecycle and bidirectional audio streaming protocol for the voice-to-voice translation demo. Designed for FastAPI/WebSocket and duplex pipeline consumers.

### Message Types

#### SessionStart
Initiates a new translation session.
- `session_id` (str): unique session identifier
- `timestamp_ms` (float): server time, milliseconds, must be finite and ≥ 0
- `source_lang` (str): source language code (e.g., "vi")
- `target_lang` (str): target language code (e.g., "en")
- `max_queue_size` (int, default=100): backpressure bound per direction

#### AudioChunk
Bidirectional audio frame with monotonic sequence and timestamp.
- `session_id` (str): must match active session
- `direction` (Direction): "a2b" or "b2a"
- `seq` (int): monotonic per direction, starting at 0; gaps tolerated, stale/duplicates rejected
- `timestamp_ms` (float): frame time, must be ≥ 0 and finite
- `payload` (bytes): PCM audio frame
- `is_final` (bool, default=False): signals last chunk before SessionEnd

#### SessionEnd
Ends session normally.
- `session_id` (str)
- `timestamp_ms` (float)
- `reason` (str): "completed" or "cancelled"

#### ErrorMessage
Transport or processing failure.
- `session_id` (str)
- `timestamp_ms` (float)
- `code` (ErrorCode): INVALID_MESSAGE, STALE_SEQUENCE, DUPLICATE_SEQUENCE, SESSION_NOT_ACTIVE, BACKPRESSURE_EXCEEDED, TIMEOUT, INTERNAL_ERROR
- `detail` (str): error context

#### CancelSession
Cancel active session; clears queues and sequence state.
- `session_id` (str)
- `timestamp_ms` (float)

#### ResumeSession
Resume session after reconnect; client sends last acknowledged sequence per direction to skip stale chunks.
- `session_id` (str)
- `timestamp_ms` (float)
- `last_seq_a2b` (int): -1 if none received yet
- `last_seq_b2a` (int): -1 if none received yet

### Contract Guarantees

1. **Session Lifecycle**: idle → active → (completed | cancelled | error)
2. **Monotonic Sequence**: per direction; no duplicates accepted; gaps tolerated but tracked
3. **Stale Detection**: sequence ≤ last received rejected with ErrorCode.STALE_SEQUENCE
4. **Backpressure**: queue size bounded by max_queue_size; excess raises BackpressureError
5. **Cancellation**: clears queues, resets sequence state, no reconnect without explicit ResumeSession
6. **Reconnect**: ResumeSession advances expected sequence to last_seq + 1; drops stale chunks
7. **Bidirectional Independence**: a2b and b2a sequences tracked separately
8. **Timestamps**: all finite, non-negative, milliseconds; no monotonicity requirement across messages
9. **Text ASR/NMT**: internal to backend pipeline; protocol does not expose transcripts

### Validation

All message types validated by `protocol.validation.MessageValidator` before processing:
- Type checks, required fields, enum membership
- Sequence and timestamp bounds
- Session state preconditions

### Testing

- `protocol/test_messages.py`: message validation fixtures and edge cases
- `protocol/test_session_manager.py`: session lifecycle, sequence ordering, backpressure, reconnect, cancellation

Run: `python -m pytest protocol/test_*.py -v`
