# Computer rewrite

This tree is the replacement architecture for `dev-computer`: a Python service and a Windows operator application. The legacy `backend/`, `protocol/`, and `android/` trees remain untouched while the replacement reaches its first verified vertical slice.

## Boundaries

- `server/` owns session lifecycle, protocol validation, duplex routing, provider ports, and observability.
- `desktop/` will own the Windows operator UI and platform audio adapters.
- `shared-fixtures/` contains language-neutral wire fixtures consumed by Python and Kotlin tests.

The server never exposes ASR or NMT text on the audio transport. The first implementation uses deterministic fake providers and local collectors. Controlled VoIP source/sink adapters are a separate gate; speaker playback is not evidence of outbound call-track injection.

## Run the local slice

```text
python -m uvicorn computer.server.app:app --host 127.0.0.1 --port 8765
```

The current pipeline is a deterministic opaque-frame transform used to prove
session, sequencing, cancellation, and duplex routing. It is not real ASR,
NMT, TTS, VoIP injection, or a latency result.

## Development order

1. Versioned JSON control contract and binary audio frame contract.
2. Server-owned lifecycle with explicit reconnect grace semantics.
3. Independent A→B and B→A bounded pipelines.
4. Windows operator app connected to localhost.
5. Controlled VoIP adapter and real provider capability probes.
6. Port the verified shared contract and state machine to `dev-mobile` using Kotlin/Jetpack Compose.
