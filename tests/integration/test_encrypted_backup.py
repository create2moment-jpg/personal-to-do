import struct
from pathlib import Path

import pytest

from ppos.application.ports import TaskQuery
from ppos.bootstrap import Container, build_container
from ppos.infrastructure.backup import create_backup, read_manifest, restore_backup
from ppos.infrastructure.backup_crypto import (
    CHUNK,
    BackupCryptoError,
    decrypt_file,
    encrypt_file,
    is_encrypted,
)
from ppos.infrastructure.config import Settings
from ppos.shared.clock import FixedClock
from tests.conftest import POSIX_MODES

PASS = "correct horse battery staple"


def test_encrypted_backup_round_trip(
    container: Container, settings: Settings, clock: FixedClock, tmp_path: Path
) -> None:
    container.tasks.create("Secret plan for Q1")
    info = create_backup(settings, label="enc", passphrase=PASS)
    assert info.path.name.endswith(".tar.gz.enc") and is_encrypted(info.path)
    assert not list(settings.backups_dir.glob("*.tar.gz"))  # no plaintext archive left behind
    assert b"Secret plan" not in info.path.read_bytes()
    assert not POSIX_MODES or info.path.stat().st_mode & 0o777 == 0o600

    with pytest.raises(BackupCryptoError, match="passphrase is needed"):
        read_manifest(info.path)
    with pytest.raises(BackupCryptoError, match="wrong passphrase"):
        read_manifest(info.path, "not the right passphrase")
    assert read_manifest(info.path, PASS)["label"] == "enc"

    other = Settings(local_data_dir=tmp_path / "restored", web_dist_dir=tmp_path / "x")
    restore_backup(other, info.path, passphrase=PASS)
    c2 = build_container(other, clock)
    assert [t.title for t in c2.tasks.find(TaskQuery())] == ["Secret plan for Q1"]


def test_stream_detects_tampering_truncation_and_reordering(tmp_path: Path) -> None:
    src = tmp_path / "plain.bin"
    src.write_bytes(bytes(range(256)) * (CHUNK // 256 * 2 + 10))  # 3 chunks
    enc = tmp_path / "data.enc"
    encrypt_file(src, enc, PASS)
    out = tmp_path / "out.bin"
    decrypt_file(enc, out, PASS)
    assert out.read_bytes() == src.read_bytes()

    blob = bytearray(enc.read_bytes())
    header = 8 + 16 + 12 + 8
    # flip one byte in the first chunk
    bad = blob.copy()
    bad[header + 10] ^= 1
    (tmp_path / "bad.enc").write_bytes(bad)
    with pytest.raises(BackupCryptoError):
        decrypt_file(tmp_path / "bad.enc", out, PASS)
    # cut off the last chunk: the new last chunk was not sealed as "final"
    first_len = struct.unpack(">I", blob[header : header + 4])[0]
    second_at = header + 4 + first_len
    second_len = struct.unpack(">I", blob[second_at : second_at + 4])[0]
    (tmp_path / "short.enc").write_bytes(blob[: second_at + 4 + second_len])
    with pytest.raises(BackupCryptoError):
        decrypt_file(tmp_path / "short.enc", out, PASS)
    # swap the first two chunks
    first = blob[header:second_at]
    second = blob[second_at : second_at + 4 + second_len]
    swapped = blob[:header] + second + first + blob[second_at + 4 + second_len :]
    (tmp_path / "swap.enc").write_bytes(swapped)
    with pytest.raises(BackupCryptoError):
        decrypt_file(tmp_path / "swap.enc", out, PASS)
    with pytest.raises(BackupCryptoError, match="at least"):
        encrypt_file(src, enc, "short")
