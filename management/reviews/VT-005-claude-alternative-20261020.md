# VT-005 Alternative Assessment — Permissive VoIP Media Path

Cập nhật: 2026-10-20
Worker: Claude research worker (VT-005 worktree)
Scope: Evaluate permissive-license VoIP candidates with bidirectional frame hooks

---

## Executive Summary

Assessed 10 VoIP candidates for A-only control with bidirectional audio substitution. Three permissive-license options emerge:

1. **Baresip** (BSD 3-Clause): minimal SIP stack, modular audio interface, pure C
2. **WebRTC Native** (BSD/Apache 2.0): battle-tested on Android, AudioDeviceModule hook
3. **libdatachannel** (MIT): WebRTC DataChannel + media tracks, C++ API

**PJSIP** (GPLv2 + commercial dual-license) remains most mature with validated Android build; legal path requires Teluu commercial license negotiation.

No candidate has real-call evidence yet; all require JNI wrapper + device proof.

---

## Investigation Scope

- **Constraint**: Only A controls translation tool; B uses standard VoIP client
- **Requirement**: Bidirectional frame hooks (outbound mic→encode, decode→render)
- **License**: Prefer MIT/BSD/Apache 2.0; avoid GPL without commercial path
- **Platform**: Android NDK arm64-v8a, API 21+
- **Out of scope**: Arbitrary Android app interception (sandbox limitation acknowledged)

---

## Candidates Assessed

### 1. Baresip (BSD 3-Clause) — **Recommended for spike**

**Source**: https://github.com/baresip/baresip
**License**: BSD 3-Clause ✅
**Description**: Minimal SIP stack with modular audio interface

**API Evidence**:
- `ausrc` module: audio source (capture) with frame callback
- `auplay` module: audio playback with frame callback
- Module architecture allows custom ausrc/auplay to intercept before codec
- Documentation: https://github.com/baresip/baresip/tree/main/docs

**Android Feasibility**:
- Pure C; compiles with NDK (no large frameworks)
- Minimal dependencies: libre (library utilities), librem (real-time media)
- Community Android patches exist (not official AAR)

**Media Hooks**:
- Outbound: custom `ausrc` module feeds frames; can inject translated audio pre-encode
- Inbound: custom `auplay` module receives decoded frames; can substitute before speaker

**Frame Format**: PCM (configurable sample rate); codec negotiation via SDP

**Signaling**: SIP (INVITE/ACK/BYE); requires SIP server or peer-to-peer mode

**Peer Requirement**: B needs SIP-compatible client (standard softphone, SIP.js, etc.)

**Blocker**: No official Android AAR or JNI wrapper; requires custom integration and device test

**Gate Coverage**:
- A: Baseline VoIP — requires SIP peer + device test
- B: Outbound substitution — requires ausrc module + fixture PCM injection + B hears fixture
- C: Inbound substitution — requires auplay module + fixture replacement + A hears substitute
- D: Full duplex — requires simultaneous bidirectional test
- E: Dual-end trace — requires consent + checksum/timestamp proof

**Risk**: Module integration complexity unknown; no pre-built Android sample

---

### 2. WebRTC Native (BSD/Apache 2.0) — **Fallback; battle-tested**

**Source**: https://webrtc.googlesource.com/src/
**License**: BSD 3-Clause + Apache 2.0 ✅
**Description**: Google's WebRTC C++ implementation; widely used in Chrome/Android

**API Evidence**:
- `AudioDeviceModule`: custom audio capture/render device
- `AudioProcessing` pipeline: frame-level access pre/post codec
- `PeerConnection` API: WebRTC signaling (offer/answer)
- Documentation: https://webrtc.googlesource.com/src/+/refs/heads/main/api/

**Android Feasibility**:
- Official Android support via NDK
- Pre-built AAR available (Google Maven)
- Bazel build system (complex; requires wrapper for Gradle)

**Media Hooks**:
- Outbound: custom `AudioDeviceModule::RecordedDataIsAvailable` callback → inject translated PCM
- Inbound: custom `AudioDeviceModule::PlayoutData` callback → substitute decoded PCM before speaker

**Frame Format**: PCM (16 kHz default); codec negotiation via SDP (Opus, iSAC, etc.)

**Signaling**: WebRTC offer/answer (SDP) via data channel or WebSocket

**Peer Requirement**: B needs WebRTC client (browser, mobile app, or server peer)

**Blocker**: Large codebase; JNI complexity; potential clash with system WebRTC on Android

**Gate Coverage**:
- A–E: Same as Baresip; all require device + peer test

**Risk**: Integration overhead; binary size (~10 MB+ for AAR)

---

### 3. libdatachannel (MIT) — **Research candidate**

**Source**: https://github.com/paullouisarana/libdatachannel
**License**: MIT ✅
**Description**: WebRTC DataChannel + media tracks via C++ API

**API Evidence**:
- `rtcDataChannel` for signaling
- `onTrack` callback for media track ingress
- `onFrame` callback for audio frame access
- Documentation: https://libdatachannel.org/

**Android Feasibility**:
- Native C++; requires CMake + NDK
- Works with arm64-v8a, android-21+
- No out-of-box Android AAR; requires JNI wrapper

**Media Hooks**:
- Inbound: `onFrame` callback provides decoded PCM
- Outbound: `sendFrame` or track-level encoder hook (documentation sparse)

**Frame Format**: PCM (sample rate negotiable)

**Signaling**: WebRTC offer/answer via data channel

**Peer Requirement**: B needs WebRTC peer

**Blocker**: Outbound frame injection unclear from documentation; JNI wrapper unverified; no Android sample

**Gate Coverage**: Unclear; requires spike to validate bidirectional hooks

---

### 4. PJSIP 2.17 (GPLv2 / Commercial Dual-License) — **Already validated build**

**Source**: https://www.pjsip.org/ (tag 2.17)
**License**: GPLv2 ⚠️ OR commercial license from Teluu
**Description**: Mature SIP/VoIP stack with conference bridge

**API Evidence**:
- `pj::AudioMediaPort::onFrameRequested`: hook to provide outbound frame
- `pj::AudioMediaPort::onFrameReceived`: hook to receive inbound frame
- Documentation: https://docs.pjsip.org/en/latest/api/generated/pjsip/group/group__PJSUA2__MED.html

**Android Feasibility**:
- ✅ **Already validated**: CMake + NDK arm64-v8a build successful
- ✅ `llvm-nm -C libpjsua2.a` confirms `AudioMediaPort` symbols
- Static library `libpjsua2.a` size: 8,589,788 bytes

**Media Hooks**:
- ✅ Bidirectional frame callbacks confirmed via spike (see `research/audio_route/pjsip-android-spike.md`)

**Frame Format**: PCM (configurable via conference bridge)

**Signaling**: SIP (INVITE/ACK/BYE)

**Peer Requirement**: B needs SIP-compatible client

**Blocker**:
- ⚠️ **Legal**: GPLv2 license requires either (1) open-source entire app under GPL, or (2) obtain commercial license from Teluu
- No JNI wrapper, signaling endpoint, or peer B yet
- No device proof (gates A–E blocked)

**Gate Coverage**: All gates A–E feasible after legal/commercial license resolution

**Risk**: Legal/commercial negotiation timeline unknown

---

### 5. Linphone (GPL v3 / Commercial Dual-License)

**Source**: https://www.linphone.org/
**License**: GPL v3 ⚠️ OR commercial license from Belledonne Communications
**Description**: Modern SIP/VoIP client with Belle-SIP + ms-media-streams

**API Evidence**:
- `RtpSession` with frame callbacks
- `MSFilter` architecture for audio processing
- Android support via native build + AAR

**Android Feasibility**:
- Official Android AAR available
- Gradle integration supported

**Media Hooks**:
- Bidirectional frame access via `MSFilter` graph

**Blocker**:
- ⚠️ **Legal**: GPL v3 requires commercial license for proprietary app
- Larger codebase than PJSIP

**Gate Coverage**: All gates A–E feasible after commercial license

**Risk**: Similar to PJSIP; legal path required

---

### 6. Coturn (BSD) — **Not suitable**

**Source**: https://github.com/coturn/coturn
**License**: BSD 3-Clause
**Blocker**: Architecture mismatch; relay-focused, no frame-level hooks

---

### 7. OPUS (BSD) — **Codec only; not suitable**

**Source**: https://github.com/xiph/opus
**License**: BSD
**Blocker**: Codec only; no VoIP signaling or call control

---

### 8. libsrtp (BSD) — **Encryption only; not suitable**

**Source**: https://github.com/cisco/libsrtp
**License**: BSD 3-Clause
**Blocker**: RTP encryption; no frame capture/injection

---

### 9. Jami / GNU Ring (GPL v3) — **Not permissive**

**Source**: https://jami.net/
**License**: GPL v3 ⚠️
**Blocker**: GPL v3 without commercial option disclosed

---

### 10. Telegram / Signal — **Closed source; not viable**

**Blocker**: Closed source; cannot audit or integrate

---

## Evidence Classification

### Source/API Evidence ✅

- **Baresip**: ausrc/auplay module interface documented; source available
- **WebRTC Native**: AudioDeviceModule API documented; Google reference available
- **libdatachannel**: onTrack/onFrame callbacks documented; MIT source available
- **PJSIP**: AudioMediaPort API documented; spike confirmed symbols via `llvm-nm`

### Build Evidence

- **PJSIP**: ✅ CMake + NDK build successful; static library inspected
- **Baresip**: ⚠️ Pure C; NDK feasible but no Android sample validated
- **WebRTC Native**: ✅ Official Android AAR available; Bazel build documented
- **libdatachannel**: ⚠️ CMake + NDK feasible; no Android build validated

### Real Call Evidence ❌

- **All candidates**: No real VoIP call executed; no device proof
- **Blocker**: `adb devices` empty; no paired device; no peer B; no SIP/WebRTC server
- **Gates A–E**: Blocked pending device + peer + controlled VoIP integration

---

## Recommendations

### Immediate Next Step (VT-005 continuation)

**Spike Baresip** (BSD 3-Clause) as lowest-friction permissive option:

1. Checkout Baresip source (tag stable/1.1 or latest)
2. Build native libraries (`libre`, `librem`, `baresip`) for arm64-v8a via NDK
3. Create custom `ausrc` module for outbound frame interception (inject translated PCM)
4. Create custom `auplay` module for inbound frame interception (substitute before speaker)
5. Validate symbols via `llvm-nm`
6. Document frame format, sample rate, latency, and JNI binding requirements
7. Update `research/audio_route/` with Baresip spike results
8. **No commit of Baresip source/binaries to repo** (keep spike external; document build steps)

**Effort estimate**: 1–2 days for native build + module spike; no real call yet

---

### Parallel Track (Legal Clarification)

**PJSIP commercial license inquiry** with Teluu:

- Already validated native build + media hooks
- Reduces technical risk (known API)
- Commercial license terms TBD; may be acceptable for thesis/research prototype

**Decision gate**: If commercial license is acceptable (cost, terms, timeline), reuse existing PJSIP spike and close VT-005 faster.

---

### Fallback (If Baresip spike fails)

**WebRTC Native** (Google, battle-tested):

- Official Android support
- Larger binary size (~10 MB)
- More complex JNI integration
- Use only if Baresip and PJSIP both blocked

---

## VT-005 Gate Status

| Gate | Description | Status | Evidence |
|------|-------------|--------|----------|
| A | Baseline VoIP call (A/B) | ❌ Blocked | No device, no peer, no SIP/WebRTC server |
| B | Outbound substitution (B hears fixture) | ❌ Blocked | No controlled VoIP integration |
| C | Inbound substitution (A hears fixture) | ❌ Blocked | No controlled VoIP integration |
| D | Full duplex (simultaneous bidirectional) | ❌ Blocked | No call test |
| E | Dual-end trace (checksum/timestamp) | ❌ Blocked | No call test |

**Blocker summary**: Device proof requires:
1. ADB device paired and connected
2. Controlled VoIP SDK integrated (Baresip, PJSIP, or WebRTC)
3. JNI wrapper for audio hooks
4. Peer B client (SIP softphone or WebRTC peer)
5. SIP server or WebRTC signaling server (or peer-to-peer mode)

---

## Skipped / Not Checked

- **Baresip native build on Windows NDK**: Assumed feasible (pure C); not executed
- **libdatachannel outbound frame injection**: Documentation unclear; not validated
- **WebRTC AudioDeviceModule JNI wrapper**: Android sample exists but not audited
- **PJSIP commercial license terms**: Not contacted; legal path unknown
- **Real latency measurement**: No call test; <1s target not verified

---

## Risks

- **Baresip**: No official Android support; community patches unverified
- **WebRTC**: Large binary; JNI complexity; potential system WebRTC clash
- **PJSIP**: Legal/commercial license timeline unknown; may block product
- **All candidates**: Device proof, peer test, and latency measurement required before Done

---

## Attachments

- Existing spike: `research/audio_route/pjsip-android-spike.md` (PJSIP GPLv2 build)
- Route harness: `research/audio_route/route_harness.py` (13 unit tests pass)
- VT-005 ticket: `management/backlog/VT-005.md`

---

**Next action**: Await GM/manager decision on Baresip spike vs. PJSIP legal inquiry vs. WebRTC fallback.
