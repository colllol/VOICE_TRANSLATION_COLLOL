# VT-005 Windows VoIP Feasibility Design

## Intent
Validate a controlled Windows SIP call path for the community R&D demo before adapting the approved media behavior to Android. Only A operates translation controls; B joins with an ordinary SIP client.

## Contract
- `a2b` and `b2a` are independent media directions and sequence spaces.
- Outbound media from A is replaced with translated voice before the VoIP encoder sends it to B.
- Inbound media from B is replaced with translated voice before it reaches A's speaker.
- ASR transcripts and NMT text remain internal and never enter the audio transport.
- On translation/provider failure, do not leak untranslated audio into the translated call path; make failure and stop behavior explicit and return to ordinary call audio only when A stops translation.
- Initial demo platform: Windows on A, B uses a standard SIP softphone. Initial codec: PCM at the provider boundary; select negotiated VoIP codec after spike compatibility and quality measurements.

## Approaches
1. Baresip first: BSD-3-Clause SIP user agent with Windows WASAPI support and modular audio drivers. Validate whether a custom audio module can replace PCM at the required pre-encode and pre-render points, and whether dependencies can be built and packaged.
2. PJSIP/PJSUA2 fallback: mature SIP stack with documented bidirectional `AudioMediaPort` callbacks. Use only under the community project's GPL-compatible distribution terms; record third-party notices and review the exact dependency licenses. Do not bundle binaries before that review.

No Android work in this spike. Do not select WebRTC Native for the initial SIP-client demo.

## Spike and acceptance
First verify a usable Windows C/C++ compiler, CMake, Ninja, Git and network access. Then probe Baresip build and custom source/playback module hooks. If blocked, record exact toolchain/build error and evaluate the same media boundary in PJSIP/PJSUA2 without distributing artifacts. A successful compile or synthetic harness is feasibility evidence only.

Call acceptance requires A calling B's ordinary SIP client and separately proving: B receives the translated A voice; A hears translated voice from B before local playback; both directions work without sequence crossover; stop restores the normal call path; provider/backend failure does not leak raw audio; lifecycle cleanup succeeds. Measure end-to-end directional latency, interruptions and intelligibility. No target is deemed met without measurements and owner evidence. Preserve only metadata/results; do not store personal audio, transcripts or credentials.

## Boundaries and open gate
This document approves a Windows-first SDK spike, not production integration or Android implementation. Before implementation, review this design and produce a task plan. License, exact PCM/media callback format, codec, call signaling/deployment, failure fallback semantics and real-call peer setup must be confirmed by evidence during the spike and escalated if they change this contract.
