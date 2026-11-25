# VT-005 Windows VoIP Spike Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Establish evidence whether Baresip or PJSIP can provide the approved bidirectional media boundary for a Windows SIP call controlled by A.

**Architecture:** Keep the existing route contract and harness unchanged. Add only a reproducible Windows feasibility report and, if toolchain permits, build/hook evidence; no product SDK, binaries, credentials, audio recordings, or Android integration.

**Tech Stack:** Baresip/libre, CMake, Ninja, Windows C/C++ toolchain; PJSIP/PJSUA2 fallback; Python route tests.

**Spec:** `research/audio_route/windows-voip-design.md`

## Global Constraints
- Only A controls translation; B uses an ordinary SIP client.
- Replace A outbound audio before encoding/sending and replace B inbound audio before A speaker output.
- Keep `a2b` and `b2a` independent; transcript/NMT text stays internal.
- Preserve unrelated dirty files and runtime databases; do not bundle dependency artifacts.
- Windows spike first; no Android implementation.

## Review Focus
- Custom media hook must be at pre-encode and pre-render PCM boundaries, not merely local playback.
- Failure path must not leak untranslated audio while translation mode is active.
- Baresip dependency/build and module API claims must be verified against retrieved/build evidence.
- PJSIP GPL/commercial dual-license terms must not be represented as approved distribution.
- Compile/synthetic tests must not be described as a real call; report peer/device prerequisites.

---

### Task 1: Verify prerequisites and Baresip feasibility

**Files:**
- Read: `research/audio_route/windows-voip-design.md`, `research/audio_route/feasibility.md`
- Create: `research/audio_route/windows-voip-spike.md`

- [x] Discover the UCRT64 toolchain, confirm GitHub access, and identify Baresip as the SIP client for the loopback fixture.
- [x] Inspect official Baresip source/docs for the Windows driver and custom audio module APIs.
- [x] Build in scratch and verify bidirectional replacement with synthetic audio over Windows SIP/RTP loopback.
- [ ] Verify WASAPI capture/playback and translation with B on a separate SIP client.

### Task 2: Evaluate fallback and contract harness

**Files:**
- Read: `research/audio_route/pjsip-android-spike.md`, `research/audio_route/route_harness.py`, `research/audio_route/test_route.py`
- Create/update: `research/audio_route/windows-voip-spike.md`

- [x] Verify PJSIP API/license reference and record the limits of the existing evidence.
- [x] Run the existing synthetic route harness and record the result.
- [x] Record real-call acceptance prerequisites and outstanding gates.

### Task 3: Final scope verification

- [ ] Check `git diff --check` and verify only scoped research files changed in this task.
- [ ] Do not mark VT-005 done or claim call acceptance without A/B real call evidence.
