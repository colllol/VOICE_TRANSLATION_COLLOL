from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthResponse:
    service: str = "voice-translation-backend"
    status: str = "ok"
    protocol_version: str = "v0"


def health_payload() -> dict[str, str]:
    return {
        "service": HealthResponse.service,
        "status": HealthResponse.status,
        "protocol_version": HealthResponse.protocol_version,
    }
