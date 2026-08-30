"""Phase 8: audio mixer loudness normalization + sidechain ducking graphs."""

from pathlib import Path

from voice.audio_mixer import AudioMixer


def _mixer(tmp_path, **kwargs):
    cfg = {"music": {
        "enabled": kwargs.pop("enabled", True),
        "music_file": kwargs.pop("music_file", str(tmp_path / "bg.mp3")),
        "volume": kwargs.pop("volume", 0.15),
        "ducking": kwargs.pop("ducking", True),
    }}
    cfg["voice"] = {"loudness_target": kwargs.pop("loudness_target", -14.0)}
    return AudioMixer(cfg)


def test_with_music_uses_sidechain_ducking_and_loudnorm(tmp_path):
    (tmp_path / "bg.mp3").write_bytes(b"dummy")
    mixer = _mixer(tmp_path)
    inputs, graph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3")

    assert "-stream_loop" in inputs
    assert "sidechaincompress" in graph
    assert "loudnorm=I=-14.0" in graph
    assert "amix=inputs=2" in graph
    assert "volume=0.15" in graph
    assert "[1:a]" in graph and "[2:a]" in graph


def test_with_music_voice_index_shifts_graph_labels(tmp_path):
    (tmp_path / "bg.mp3").write_bytes(b"dummy")
    mixer = _mixer(tmp_path, loudness_target=None)
    _, graph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3", voice_index=3)

    assert "[3:a]" in graph
    assert "[4:a]" in graph
    assert "[1:a]" not in graph


def test_ducking_disabled_falls_back_to_blend(tmp_path):
    (tmp_path / "bg.mp3").write_bytes(b"dummy")
    mixer = _mixer(tmp_path, ducking=False)
    _, graph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3")

    assert "sidechaincompress" not in graph
    assert "amix=inputs=2" in graph


def test_loudnorm_disabled_uses_volume_passthrough(tmp_path):
    (tmp_path / "bg.mp3").write_bytes(b"dummy")
    mixer = _mixer(tmp_path, loudness_target=None)
    _, graph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3")

    assert "loudnorm" not in graph
    assert "[1:a]volume=1.0" in graph
    assert "asplit=2" in graph



def test_music_fades_out_when_duration_given(tmp_path):
    (tmp_path / "bg.mp3").write_bytes(b"dummy")
    mixer = _mixer(tmp_path)
    _, graph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3", voice_duration=30.0)
    assert "afade=t=out:st=28.00:d=2.0" in graph


def test_no_music_returns_clean_voice_passthrough_when_loudness_off(tmp_path):
    cfg = {"music": {"enabled": False}, "voice": {"loudness_target": None}}
    mixer = AudioMixer(cfg)
    inputs, graph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3")
    assert inputs == []
    assert "[1:a]volume=1.0[aout]" in graph