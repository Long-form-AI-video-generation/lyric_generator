from __future__ import annotations

import pytest

from backend.core.errors import ValidationAppError
from backend.services.media import sanitize_filename, sniff_audio_type, sniff_image_type


def test_sanitize_filename_removes_paths_and_unsafe_chars() -> None:
    assert sanitize_filename("../My Song !!.mp3") == "My-Song-.mp3"
    assert sanitize_filename("") == "upload"


def test_sniff_audio_type_accepts_wav_and_mp3_magic() -> None:
    assert sniff_audio_type(b"RIFF\x00\x00\x00\x00WAVEfmt ", "song.wav") == ".wav"
    assert sniff_audio_type(b"ID3\x04\x00\x00\x00", "song.mp3") == ".mp3"
    assert sniff_audio_type(b"\xff\xfb\x90d", "song.mp3") == ".mp3"


def test_sniff_audio_type_rejects_unsupported_file() -> None:
    with pytest.raises(ValidationAppError, match="MP3 or WAV"):
        sniff_audio_type(b"not audio", "song.txt")


def test_sniff_image_type_accepts_supported_images() -> None:
    assert sniff_image_type(b"\xff\xd8\xff\xe0", "bg.jpg") == ".jpg"
    assert sniff_image_type(b"\x89PNG\r\n\x1a\n\x00", "bg.png") == ".png"
    assert sniff_image_type(b"RIFF\x00\x00\x00\x00WEBP", "bg.webp") == ".webp"

