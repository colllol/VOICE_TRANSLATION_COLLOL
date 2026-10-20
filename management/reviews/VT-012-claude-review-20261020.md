# VT-012 — Claude Review 20261020

Cập nhật: 2026-10-20

## Phạm vi review

Đọc AGENTS.md, OPERATING-MODEL, VT-012, VT-003 audit, backend/providers và tests. Reviewer: Claude independent. Không sửa production source. Xác minh interface semantics, fake determinism/honesty, fail-closed real providers, metadata meaning/license/corpus provenance, secret handling, streaming claims, audio format claims, internal text containment, và test quality.

## Tóm tắt

**Kết luận tổng thể**: Implementation đạt acceptance criteria với các vấn đề nghiêm trọng về semantics và misleading claims cần sửa trước khi tích hợp production.

**Commits kiểm tra**:
- 0ebeb42: backend: implement VT-012 ASR NMT TTS provider adapters
- c68d187: backend: smoke test for providers with session integration

**Tests pass**: 35/35 unit tests pass (pytest backend/providers/test_providers.py -v)

---

## Findings

### CRITICAL-1: PCM format claim không có định nghĩa cụ thể

**File**: `backend/providers/base.py:45`

**Evidence**:
```python
def synthesize(self, text: str, target_lang: str) -> bytes:
    """Synthesize text to audio bytes (PCM format). Returns streaming-capable bytes."""
```

**Issue**: Docstring claim "PCM format" nhưng không định nghĩa:
- Sample rate (16kHz? 44.1kHz? 48kHz?)
- Bit depth (16-bit? 24-bit?)
- Channels (mono? stereo?)
- Endianness (little-endian? big-endian?)
- Signed vs unsigned samples

**Real behavior**: FakeTTSProvider trả về `b"FAKE_PCM" + synthetic_bytes` không phải PCM thực. Real providers chưa implement nên không có format thực tế.

**Impact**: Caller không thể decode audio. Android AudioTrack cần format chính xác để phát.

**Fix required**:
1. Thay docstring thành "Synthesize text to audio bytes. Format defined by implementation."
2. Hoặc thêm `AudioFormat` dataclass với `sample_rate`, `channels`, `bit_depth` và return `tuple[bytes, AudioFormat]`
3. Update fake provider để mock format metadata hoặc loại bỏ misleading "PCM" claim

---

### CRITICAL-2: Streaming claim không có streaming API

**File**: `backend/providers/config.py:15`, `backend/providers/base.py:48-50`

**Evidence**:
```python
@dataclass(frozen=True)
class ProviderConfig:
    supports_streaming: bool

def supports_streaming(self) -> bool:
    """Check if provider supports streaming synthesis."""
    return self.config.supports_streaming
```

**Issue**:
- `supports_streaming` flag tồn tại nhưng không có streaming method
- `synthesize()` trả về `bytes` hoàn chỉnh, không phải iterator/async generator/callback
- Fake providers set `supports_streaming=True` nhưng không stream
- Tests không verify streaming behavior, chỉ check flag

**Real behavior**: Tất cả providers đều batch-mode. Flag `supports_streaming=True` là misleading.

**Impact**: Code tương lai dựa vào flag này sẽ expect streaming API không tồn tại.

**Fix required**:
1. Loại bỏ `supports_streaming` field và method cho đến khi có streaming implementation
2. Hoặc thêm `synthesize_stream()` method return `Iterator[bytes]` hoặc `AsyncIterator[bytes]`
3. Nếu giữ flag: đổi tên thành `model_supports_streaming` và document rõ "indicates model capability, not current API behavior"

---

### HIGH-1: Fake provider contract test misleading về real behavior

**File**: `backend/providers/fake.py:11-19`, `backend/providers/test_providers.py:161-180`

**Issue**:
- FakeASRProvider return deterministic text based on audio length: `f"test utterance {count}"`
- Test `test_transcribe_deterministic` chỉ verify same input → same output
- Không test error conditions real ASR có: malformed audio, unsupported codec, language mismatch
- Fake không validate audio format, accept bất kỳ bytes nào

**Real behavior**: Real ASR cần valid audio format, có thể fail với codec/rate mismatch.

**Impact**: Tests pass nhưng không bảo vệ khỏi integration failures với real providers.

**Recommendation** (không block merge): Thêm test comments rõ "Fake providers test contract only, not real provider error modes. Real provider integration requires separate testing with valid audio fixtures."

---

### HIGH-2: Real provider fail-closed implementation không complete

**File**: `backend/providers/real.py:16-20, 30-34, 49-53`

**Evidence**: Real providers raise `ConfigError` in methods, không tại `__init__`

**Issue**:
- `RealASRProvider.__init__` và `RealNMTProvider.__init__` succeed but `_model = None`
- Chỉ fail khi call `transcribe()` hoặc `translate()`
- `RealTTSProvider.__init__` fail early nếu missing `TTS_API_KEY` — inconsistent
- Test `test_real_tts_without_api_key_raises` manipulates `os.environ` nhưng không restore (có thể affect other tests nếu run parallel)

**Impact**:
- Provider instance có thể được tạo nhưng fail sau đó
- Không consistent về khi nào fail
- Test có potential side effect

**Fix required**:
1. Đồng nhất: tất cả real providers nên fail tại `__init__` nếu missing config
2. Hoặc document rõ rationale cho lazy validation
3. Test cần cleanup: `os.environ` restore sau assertion hoặc dùng pytest fixture

---

### MEDIUM-1: Metadata fields không có validation cụ thể

**File**: `backend/providers/config.py:17-26`

**Evidence**:
```python
def validate(self) -> None:
    if not self.name or not self.name.strip():
        raise ValueError("provider name must be non-empty")
    # ... similar for model_revision, license, corpus
```

**Issue**:
- `license` field chấp nhận arbitrary string: "MIT", "proprietary", bất cứ gì
- `corpus` field không có enum hoặc validation
- `model_revision` không có format constraint
- Không có central registry để verify license/corpus validity

**Real behavior**: Có thể tạo config với `license="foo"` hoặc `corpus="bar"` không có nghĩa.

**Impact**: Metadata không reliable cho compliance audit. VT-003 cần accurate license info.

**Recommendation**:
1. Thêm `LicenseType` enum: MIT, Apache2, CC_BY_NC_4_0, Proprietary, Unknown
2. Thêm `CorpusType` enum hoặc freeform với validation pattern
3. Hoặc document rõ "metadata fields are informational only, not validated"

---

### MEDIUM-2: Internal text containment không được test

**File**: Không có test verify text không leak ra UI

**Issue**:
- ASR text và NMT text là internal
- AGENTS.md line 7: "Text ASR/NMT chỉ dùng nội bộ"
- Không có test verify text không được expose qua protocol hoặc Android UI
- `backend/test_providers_smoke.py` gọi provider methods nhưng không verify text containment

**Real behavior**: Text có thể leak nếu SessionService hoặc Android code log/display.

**Impact**: Violation của product constraint.

**Recommendation**: Thêm integration test verify:
1. SessionService không return ASR/NMT text trong response
2. Chỉ audio được trả về client
3. Logging không chứa sensitive text (hoặc có redaction)

---

### MEDIUM-3: Secret handling đúng nhưng thiếu documentation

**File**: `backend/providers/real.py:42-46`

**Evidence**:
```python
api_key = os.getenv("TTS_API_KEY")
if not api_key:
    raise ConfigError(...)
```

**Positive**: Secret được read từ environment variable, không hardcode.

**Issue**:
- Không có documentation về where to set `TTS_API_KEY`
- README hoặc setup guide không mention environment variables
- Không có `.env.example` file
- AGENTS.md line 12 says "không commit secret" nhưng không hướng dẫn proper setup

**Impact**: Developer không biết cách configure real providers.

**Recommendation**: Tạo `backend/providers/README.md` hoặc update root README với:
```markdown
## Provider Configuration

Real providers require environment variables:
- `TTS_API_KEY`: Google Cloud TTS API key (or equivalent)
- `ASR_MODEL_PATH`: Path to Faster-Whisper weights (future)
- `NMT_MODEL_PATH`: Path to NLLB-200 weights (future)

Never commit these to git. Use `.env` file (gitignored) or system environment.
```

---

### LOW-1: Test suite không có negative test cho invalid config construction

**File**: `backend/providers/test_providers.py:16-72`

**Evidence**: Tests có `test_empty_name_raises`, `test_empty_license_raises`, etc.

**Issue**: Tests chỉ verify `config.validate()` raises, không test `ProviderConfig(name="")` construction.

**Real behavior**: Dataclass construction với empty string vẫn succeed; chỉ `validate()` fail.

**Impact**: Minimal — code gọi `validate()` tại `__init__` nên safe. Nhưng test không verify provider construction flow.

**Recommendation**: Thêm test:
```python
def test_provider_construction_validates():
    config = ASRConfig(name="", ...)
    with pytest.raises(ValueError):
        ASRProvider(config)  # Should fail at __init__
```

---

### LOW-2: Smoke test import error không được handle

**File**: `backend/test_providers_smoke.py:4-6`

**Evidence**:
```python
from protocol.messages import SessionStart, AudioChunk, SessionEnd, Direction
from backend.session.service import SessionService
from backend.providers.fake import create_fake_providers
```

**Issue**: Smoke test fail với `ModuleNotFoundError: No module named 'protocol'` khi run từ backend directory.

**Real behavior**: Test cần run từ repo root với proper PYTHONPATH.

**Impact**: Developer không thể run smoke test easily. CI có thể pass nhưng local dev bị block.

**Fix required**:
1. Thêm `backend/pytest.ini` hoặc `backend/conftest.py` với `sys.path` setup
2. Hoặc document: "Run smoke tests from repo root: `python -m pytest backend/test_providers_smoke.py`"
3. Update smoke test file docstring với proper invocation

---

## Test quality assessment

**Unit tests (`backend/providers/test_providers.py`)**:
- ✅ 35 tests, comprehensive config validation
- ✅ Fake provider determinism verified
- ✅ Real provider fail-closed verified
- ✅ Error propagation tested
- ⚠️  Không test streaming behavior
- ⚠️  Không test audio format validation
- ⚠️  Fake tests không reflect real provider error modes

**Smoke tests (`backend/test_providers_smoke.py`)**:
- ✅ Session integration verified
- ✅ Duplex pipeline (A→B, B→A) tested
- ⚠️  Import error khi run từ backend dir
- ⚠️  Không verify text containment
- ⚠️  Không test error recovery

**Overall**: Test coverage đủ cho fake contract, yếu cho real integration và product constraints.

---

## Không phát hiện được (out of scope)

- Benchmark performance: VT-003 blocked on hardware/model
- Android integration: cần device test
- Real provider credentials: không có trong repo (đúng)
- Audio quality: cần human evaluation
- Voice preservation: VT-014 future work

---

## Recommendations by severity

### Must fix before merge:
1. **CRITICAL-1**: Loại bỏ hoặc clarify "PCM format" claim
2. **CRITICAL-2**: Loại bỏ hoặc implement streaming API
3. **HIGH-2**: Đồng nhất real provider fail-closed behavior
4. **LOW-2**: Fix smoke test import hoặc document proper invocation

### Should fix before production:
5. **MEDIUM-1**: Thêm metadata validation hoặc document informational-only
6. **MEDIUM-2**: Thêm text containment integration test
7. **MEDIUM-3**: Document secret handling setup

### Nice to have:
8. **HIGH-1**: Thêm comments phân biệt fake contract tests vs real integration tests
9. **LOW-1**: Thêm provider construction validation test

---

## Acceptance criteria verification

✅ **Fake providers kiểm contract**: Pass, deterministic, error propagation tested
⚠️  **Real-provider smoke**: Tests exist nhưng blocked on missing dependencies (expected)
✅ **Secrets ngoài APK**: Environment variables, không hardcode
⚠️  **Internal text không lộ UI**: Không có integration test verify, nhưng provider code không expose text ra protocol

**Overall**: 3/4 acceptance pass, 1 cần integration test.

---

## Fixes required (prioritized)

### P0 (block merge):
1. `backend/providers/base.py:45`: Change docstring from "PCM format" to "audio bytes (format implementation-defined)" hoặc define AudioFormat
2. `backend/providers/config.py:15` + `base.py:48-50`: Remove `supports_streaming` field và method, hoặc rename to `model_supports_streaming` và document
3. `backend/providers/real.py`: Unify fail-closed: all real providers fail at `__init__` if config incomplete
4. `backend/test_providers_smoke.py`: Add docstring: "Run from repo root: python -m pytest backend/test_providers_smoke.py"

### P1 (before production):
5. Create `backend/providers/README.md` với secret handling documentation
6. Add integration test verify SessionService không return internal ASR/NMT text

---

## Sign-off

Reviewer: Claude independent
Date: 2026-10-20
Model requested: opus; effective canonical model unknown (CLI metadata not verified)
Session: worktree claude-vt012-review

Không sửa production source theo instructions. Review complete.

**Verdict**: Implementation solid nhưng có misleading claims (PCM format, streaming) cần fix trước merge. Fake tests đạt contract testing baseline. Real provider integration đúng fail-closed. Text containment cần verify qua integration test với SessionService và protocol layer.
