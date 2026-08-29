from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import tempfile

import pytest


_RENAME_EXCL = 0x00000004
_COPYFILE_ALL = 0x0000000F
_COPYFILE_EXCL = 1 << 17
_COPYFILE_NOFOLLOW = (1 << 18) | (1 << 19)
_FINDER_TAGS = "com.apple.metadata:_kMDItemUserTags"
_PROBE_XATTR = "org.mediasense.apply-probe"


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def _rename_exclusive(source: Path, target: Path) -> None:
    libc = _libc()
    renamex = libc.renamex_np
    renamex.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    renamex.restype = ctypes.c_int
    if renamex(os.fsencode(source), os.fsencode(target), _RENAME_EXCL) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _copyfile_all_exclusive(source: Path, target: Path) -> None:
    libc = _libc()
    copyfile = libc.copyfile
    copyfile.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    copyfile.restype = ctypes.c_int
    flags = _COPYFILE_ALL | _COPYFILE_EXCL | _COPYFILE_NOFOLLOW
    if copyfile(os.fsencode(source), os.fsencode(target), None, flags) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _set_xattr(path: Path, name: str, value: bytes) -> None:
    libc = _libc()
    setxattr = libc.setxattr
    setxattr.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    setxattr.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(value)
    if (
        setxattr(
            os.fsencode(path),
            os.fsencode(name),
            buffer,
            len(value),
            0,
            0,
        )
        != 0
    ):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(path))


def _remove_xattr(path: Path, name: str) -> None:
    libc = _libc()
    removexattr = libc.removexattr
    removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    removexattr.restype = ctypes.c_int
    if removexattr(os.fsencode(path), os.fsencode(name), 0) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(path))


def _list_xattrs(path: Path) -> dict[str, bytes]:
    libc = _libc()
    listxattr = libc.listxattr
    listxattr.argtypes = [
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_int,
    ]
    listxattr.restype = ctypes.c_ssize_t
    size = listxattr(os.fsencode(path), None, 0, 0)
    if size < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(path))
    if size == 0:
        return {}
    names_buffer = ctypes.create_string_buffer(size)
    returned = listxattr(os.fsencode(path), names_buffer, size, 0)
    if returned < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(path))
    names = [name for name in names_buffer.raw[:returned].split(b"\0") if name]

    getxattr = libc.getxattr
    getxattr.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    getxattr.restype = ctypes.c_ssize_t
    result: dict[str, bytes] = {}
    for raw_name in names:
        value_size = getxattr(os.fsencode(path), raw_name, None, 0, 0, 0)
        if value_size < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), os.fsdecode(raw_name))
        value_buffer = ctypes.create_string_buffer(value_size)
        value_returned = getxattr(
            os.fsencode(path), raw_name, value_buffer, value_size, 0, 0
        )
        if value_returned < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), os.fsdecode(raw_name))
        result[os.fsdecode(raw_name)] = value_buffer.raw[:value_returned]
    return result


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _declared_metadata(path: Path) -> dict[str, object]:
    info = path.stat(follow_symlinks=False)
    return {
        "mode": stat.S_IMODE(info.st_mode),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mtime_ns": info.st_mtime_ns,
        "birthtime_ns": int(info.st_birthtime * 1_000_000_000),
        "flags": info.st_flags,
        "xattrs": _list_xattrs(path),
    }


def _discrepancies(source: Path, target: Path) -> list[dict[str, object]]:
    expected = _declared_metadata(source)
    observed = _declared_metadata(target)
    return [
        {"attribute": name, "expected": expected[name], "observed": observed[name]}
        for name in expected
        if expected[name] != observed[name]
    ]


def _prepared_identity(base_identity: str, discrepancies: list[dict]) -> str:
    serializable = [
        {
            "attribute": item["attribute"],
            "expected": (
                {key: value.hex() for key, value in item["expected"].items()}
                if item["attribute"] == "xattrs"
                else item["expected"]
            ),
            "observed": (
                {key: value.hex() for key, value in item["observed"].items()}
                if item["attribute"] == "xattrs"
                else item["observed"]
            ),
        }
        for item in discrepancies
    ]
    encoded = json.dumps(
        {"base": base_identity, "discrepancies": serializable},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_probe_source(path: Path) -> None:
    path.write_bytes(bytes(range(256)) * 4097)
    os.chown(path, -1, os.getgid())
    path.chmod(0o640)
    os.utime(path, ns=(1_777_777_700_000_000_000, 1_777_777_600_000_000_000))
    _set_xattr(path, _PROBE_XATTR, b"opaque-apply-probe-value")
    finder_tags = plistlib.dumps(["MediaSense Apply Probe\n6"], fmt=plistlib.FMT_BINARY)
    _set_xattr(path, _FINDER_TAGS, finder_tags)


def _fsync_file_and_parent(path: Path) -> None:
    file_descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(file_descriptor)
    finally:
        os.close(file_descriptor)
    directory_descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _publish_after_metadata_decision(
    *,
    source: Path,
    temporary: Path,
    final: Path,
    base_identity: str,
    authorized_prepared_identity: str | None,
) -> tuple[str, bool]:
    discrepancies = _discrepancies(source, temporary)
    prepared_identity = _prepared_identity(base_identity, discrepancies)
    if discrepancies and authorized_prepared_identity != prepared_identity:
        return prepared_identity, False
    _fsync_file_and_parent(temporary)
    _rename_exclusive(temporary, final)
    _fsync_file_and_parent(final)
    source.unlink()
    return prepared_identity, True


def test_darwin_same_filesystem_rename_is_atomic_and_non_overwriting(
    tmp_path: Path,
) -> None:
    if os.uname().sysname != "Darwin":
        pytest.skip("the first supported platform profile is Darwin")
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    _write_probe_source(source)
    source_identity = (source.stat().st_dev, source.stat().st_ino)
    source_digest = _digest(source)
    source_metadata = _declared_metadata(source)

    target.write_bytes(b"must-not-be-overwritten")
    with pytest.raises(OSError) as conflict:
        _rename_exclusive(source, target)
    assert conflict.value.errno == errno.EEXIST
    assert source.exists()
    assert target.read_bytes() == b"must-not-be-overwritten"

    target.unlink()
    _rename_exclusive(source, target)
    assert not source.exists()
    assert (target.stat().st_dev, target.stat().st_ino) == source_identity
    assert _digest(target) == source_digest
    assert _declared_metadata(target) == source_metadata


def _cross_filesystem_roots() -> tuple[Path, Path]:
    source_text = os.environ.get("MEDIASENSE_APPLY_CROSSFS_SOURCE_ROOT")
    target_text = os.environ.get("MEDIASENSE_APPLY_CROSSFS_TARGET_ROOT")
    if not source_text or not target_text:
        pytest.skip("set the two Apply cross-filesystem probe roots")
    source_root = Path(source_text).resolve(strict=True)
    target_root = Path(target_text).resolve(strict=True)
    if source_root.stat().st_dev == target_root.stat().st_dev:
        pytest.fail("cross-filesystem probe roots resolve to the same device")
    return source_root, target_root


@pytest.mark.local_fixture
def test_darwin_cross_filesystem_profile_preserves_declared_metadata() -> None:
    if os.uname().sysname != "Darwin":
        pytest.skip("the first supported platform profile is Darwin")
    source_root, target_root = _cross_filesystem_roots()
    source_dir = Path(
        tempfile.mkdtemp(prefix="mediasense-apply-probe-", dir=source_root)
    )
    target_dir = Path(
        tempfile.mkdtemp(prefix="mediasense-apply-probe-", dir=target_root)
    )
    try:
        source = source_dir / "source.bin"
        temporary = target_dir / ".transfer.partial"
        final = target_dir / "final.bin"
        _write_probe_source(source)
        expected_digest = _digest(source)
        expected_metadata = _declared_metadata(source)

        _copyfile_all_exclusive(source, temporary)
        assert _digest(temporary) == expected_digest
        assert _declared_metadata(temporary) == expected_metadata
        final.write_bytes(b"collision-must-survive")
        with pytest.raises(OSError) as conflict:
            _rename_exclusive(temporary, final)
        assert conflict.value.errno == errno.EEXIST
        assert source.exists() and temporary.exists()
        assert final.read_bytes() == b"collision-must-survive"
        final.unlink()
        _fsync_file_and_parent(temporary)
        _rename_exclusive(temporary, final)
        _fsync_file_and_parent(final)
        assert _digest(final) == expected_digest
        assert _declared_metadata(final) == expected_metadata
        source.unlink()
        assert not source.exists()
    finally:
        shutil.rmtree(source_dir)
        shutil.rmtree(target_dir)


@pytest.mark.local_fixture
def test_cross_filesystem_metadata_loss_requires_exact_reauthorization() -> None:
    if os.uname().sysname != "Darwin":
        pytest.skip("the first supported platform profile is Darwin")
    source_root, target_root = _cross_filesystem_roots()
    source_dir = Path(
        tempfile.mkdtemp(prefix="mediasense-apply-probe-", dir=source_root)
    )
    target_dir = Path(
        tempfile.mkdtemp(prefix="mediasense-apply-probe-", dir=target_root)
    )
    try:
        source = source_dir / "source.bin"
        temporary = target_dir / ".transfer.partial"
        final = target_dir / "final.bin"
        _write_probe_source(source)
        expected_digest = _digest(source)
        _copyfile_all_exclusive(source, temporary)
        _remove_xattr(temporary, _FINDER_TAGS)
        assert _digest(temporary) == expected_digest

        discrepancies = _discrepancies(source, temporary)
        assert [item["attribute"] for item in discrepancies] == ["xattrs"]
        original_identity = "sha256:" + "1" * 64
        changed_identity = _prepared_identity(original_identity, discrepancies)
        assert changed_identity != original_identity

        # No authorization, and stale authorization, both leave the source and
        # non-final copy in place without publishing a target.
        observed_identity, published = _publish_after_metadata_decision(
            source=source,
            temporary=temporary,
            final=final,
            base_identity=original_identity,
            authorized_prepared_identity=None,
        )
        assert observed_identity == changed_identity and not published
        assert source.exists() and temporary.exists() and not final.exists()
        observed_identity, published = _publish_after_metadata_decision(
            source=source,
            temporary=temporary,
            final=final,
            base_identity=original_identity,
            authorized_prepared_identity=original_identity,
        )
        assert observed_identity == changed_identity and not published
        assert source.exists() and temporary.exists() and not final.exists()

        # The exact changed identity models a new trusted Human authorization.
        observed_identity, published = _publish_after_metadata_decision(
            source=source,
            temporary=temporary,
            final=final,
            base_identity=original_identity,
            authorized_prepared_identity=changed_identity,
        )
        assert observed_identity == changed_identity and published
        assert final.exists() and not source.exists()
        assert _digest(final) == expected_digest
    finally:
        shutil.rmtree(source_dir)
        shutil.rmtree(target_dir)
