import math

import pytest

from research.audio_route.windows_sip_probe import verify_media


def tone(hz):
    return [round(8000 * math.sin(math.tau * hz * i / 8000)) for i in range(8000)]


@pytest.mark.parametrize('peer,hz', [('a', 700), ('b', 400)])
def test_baseline_detects_wrong_direction(peer, hz):
    verify_media(peer, tone(hz), False)
    with pytest.raises(RuntimeError, match='expected.*Hz'):
        verify_media(peer, tone(1100 - hz), False)


def test_replacement_rejects_single_leaked_sample():
    samples = [3004] * 8000
    verify_media('b', samples, True)
    samples[321] = -8000
    with pytest.raises(RuntimeError, match='1 off-target'):
        verify_media('b', samples, True)


def test_rejects_truncated_window():
    with pytest.raises(RuntimeError, match='7999 samples'):
        verify_media('a', [-3000] * 7999, True)
