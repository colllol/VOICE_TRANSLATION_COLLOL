"""Dependency-free backend import smoke; no network/model inference implied."""
from backend.health import health_payload

if __name__ == "__main__":
    result = health_payload()
    if result != {"service": "voice-translation-backend", "status": "ok", "protocol_version": "v0"}:
        raise SystemExit("Backend smoke failed")
    print("Backend import/health smoke passed; no server or model execution")
