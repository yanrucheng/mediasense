"""Video sampling characterized from AI Album c90 VideoProcessor."""

import pytest

from mediasense.precheck import sample_video_times


pytestmark = pytest.mark.characterization


def test_sampling_keeps_roughly_ten_second_interval_and_last_frame() -> None:
    assert sample_video_times(25.0) == (0.0, 10.0, 20.0, 25.0)


def test_sampling_is_bounded_to_twenty_frames_for_long_video() -> None:
    samples = sample_video_times(600.0)

    assert len(samples) == 20
    assert samples[0] == 0.0
    assert samples[-1] == 600.0
    assert samples == tuple(sorted(samples))
