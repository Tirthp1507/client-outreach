"""Tests for AudioMixer and background music ducking."""

from pathlib import Path
from voice.audio_mixer import AudioMixer


def test_audio_mixer_no_music_returns_voice_passthrough(tmp_path):
    mixer = AudioMixer({"music": {"enabled": False}})
    assert mixer.find_music_track() is None

    inputs, fgraph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3")
    assert inputs == []
    # Default config applies loudness normalization to the narration.
    assert "[1:a]loudnorm=" in fgraph
    assert fgraph.endswith("[aout]")


def test_audio_mixer_no_music_loudness_optional(tmp_path):
    cfg = {"music": {"enabled": False}, "voice": {"loudness_target": None}}
    inputs, fgraph = AudioMixer(cfg).build_audio_inputs_and_filter(tmp_path / "voice.mp3")
    assert "[1:a]volume=1.0[aout]" in fgraph


def test_audio_mixer_with_music_file(tmp_path):
    music_file = tmp_path / "bg_track.mp3"
    music_file.write_bytes(b"dummy audio data")

    mixer = AudioMixer({"music": {"enabled": True, "music_file": str(music_file), "volume": 0.15}})
    found = mixer.find_music_track()
    assert found == music_file

    inputs, fgraph = mixer.build_audio_inputs_and_filter(tmp_path / "voice.mp3")
    assert "-stream_loop" in inputs
    assert "amix=inputs=2" in fgraph
    assert "volume=0.15" in fgraph