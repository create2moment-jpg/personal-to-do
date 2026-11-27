"""Passphrase encryption for backup archives.

Format (all integers big-endian):
    magic  b"PPOSENC1"
    salt   16 bytes      scrypt salt
    n, r, p              3 x uint32 scrypt cost parameters
    prefix 8 bytes       random nonce prefix
    then chunks: uint32 length | AES-256-GCM(ciphertext + tag)

Each chunk's nonce is prefix + uint32 counter, and its associated data binds
the header, the counter and a final-chunk flag: chunks cannot be reordered,
swapped between files, or cut off without the decryption failing.
"""

from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ppos.shared.errors import PposError

# O_BINARY matters on Windows: without it os.write translates "\n" to "\r\n",
# which would corrupt encrypted output. It does not exist (and is not needed) on POSIX.
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)

MAGIC = b"PPOSENC1"
CHUNK = 1024 * 1024
SCRYPT = (2**15, 8, 1)
MIN_PASSPHRASE = 12


class BackupCryptoError(PposError):
    """Wrong passphrase, or the encrypted file was damaged or altered."""


def is_encrypted(path: Path) -> bool:
    with path.open("rb") as fh:
        return fh.read(len(MAGIC)) == MAGIC


def _key(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        passphrase.encode(), salt=salt, n=n, r=r, p=p, maxmem=256 * 1024 * 1024, dklen=32
    )


def _aad(header: bytes, counter: int, last: bool) -> bytes:
    return header + struct.pack(">I?", counter, last)


def encrypt_file(src: Path, dest: Path, passphrase: str) -> None:
    if len(passphrase) < MIN_PASSPHRASE:
        raise BackupCryptoError(f"use a passphrase of at least {MIN_PASSPHRASE} characters")
    salt, prefix = os.urandom(16), os.urandom(8)
    header = MAGIC + salt + struct.pack(">III", *SCRYPT) + prefix
    aead = AESGCM(_key(passphrase, salt, *SCRYPT))
    fd = os.open(dest, _WRITE_FLAGS, 0o600)
    with src.open("rb") as fin, os.fdopen(fd, "wb") as fout:
        fout.write(header)
        _write_chunks(fin, fout, aead, header, prefix)


def _write_chunks(
    fin: BinaryIO, fout: BinaryIO, aead: AESGCM, header: bytes, prefix: bytes
) -> None:
    counter = 0
    block = fin.read(CHUNK)
    while True:
        nxt = fin.read(CHUNK)
        last = not nxt
        sealed = aead.encrypt(
            prefix + struct.pack(">I", counter), block, _aad(header, counter, last)
        )
        fout.write(struct.pack(">I", len(sealed)) + sealed)
        if last:
            return
        block, counter = nxt, counter + 1


def decrypt_file(src: Path, dest: Path, passphrase: str) -> None:
    with src.open("rb") as fin:
        head = fin.read(len(MAGIC) + 16 + 12 + 8)
        if len(head) < len(MAGIC) + 36 or not head.startswith(MAGIC):
            raise BackupCryptoError("not an encrypted ppos backup")
        salt = head[8:24]
        n, r, p = struct.unpack(">III", head[24:36])
        prefix = head[36:44]
        aead = AESGCM(_key(passphrase, salt, n, r, p))
        fd = os.open(dest, _WRITE_FLAGS, 0o600)
        with os.fdopen(fd, "wb") as fout:
            counter = 0
            while True:
                size_raw = fin.read(4)
                if len(size_raw) < 4:
                    raise BackupCryptoError("the encrypted backup is incomplete")
                sealed = fin.read(struct.unpack(">I", size_raw)[0])
                last = fin.peek(1)[:1] == b"" if hasattr(fin, "peek") else False
                try:
                    plain = aead.decrypt(
                        prefix + struct.pack(">I", counter), sealed, _aad(head, counter, last)
                    )
                except InvalidTag as exc:
                    raise BackupCryptoError("wrong passphrase, or the backup was altered") from exc
                fout.write(plain)
                if last:
                    return
                counter += 1
