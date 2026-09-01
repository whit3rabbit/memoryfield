"""`mf pack` / `mf unpack` -- a memoryfield as one verifiable archive.

Layout (ROADMAP.md 2.4, an assumption where the spec is silent: no copy
of the spec's zip layout exists in this repo): the archive root mirrors
the field root. Pages and their subdirectories keep their relative
paths, `raw/` and `mf.sqlite3` are included by default, and everything
`mf index` skips (`.git`, virtualenvs, dotfiles) is left out. A sidecar
`<name>.memoryfield.zip.sha256` carries the digest in `sha256sum` form.

The archive is reproducible: members are written in sorted order with a
fixed timestamp, so the same field content always produces the same
digest, and a changed digest means changed content, not a re-pack.

`unpack` verifies the digest (sidecar or `--sha256`) before extracting,
refuses member paths that escape the destination, strips a single
top-level directory if every member sits under one (a folder zipped
from a file manager), and, when the archive carries an index, reports
how many pages the index disagrees with on disk. The extracted index
works as-is because `pages.filename` is field-relative.
"""
from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import db
from .db import DB_FILENAME
from .indexer import _SKIP_DIRS
from .raw import RAW_DIRNAME

SUFFIX = ".memoryfield.zip"
SIDECAR_SUFFIX = ".sha256"
# Fixed member timestamp (the ZIP epoch) so the digest tracks content only.
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


class PackVerifyError(RuntimeError):
    """The archive's digest doesn't match the sidecar or --sha256."""


class UnpackError(RuntimeError):
    """A member path escapes the destination, or the destination isn't empty."""


@dataclass
class PackResult:
    path: Path
    sha256: str
    files: int
    bytes: int

    def as_dict(self) -> dict:
        return {"path": str(self.path), "sha256": self.sha256, "files": self.files, "bytes": self.bytes}


@dataclass
class UnpackResult:
    dest: Path
    sha256: str
    verified: bool | None       # None: nothing to verify against
    files: int
    stripped_prefix: str = ""
    has_index: bool = False
    index_drift: int = 0        # pages whose on-disk sha256 != the packed index's
    index_error: str = ""       # the packed index couldn't be opened (schema version)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "dest": str(self.dest), "sha256": self.sha256, "verified": self.verified,
            "files": self.files, "stripped_prefix": self.stripped_prefix,
            "has_index": self.has_index, "index_drift": self.index_drift,
            "index_error": self.index_error, "notes": self.notes,
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _members(field_dir: Path, include_index: bool, include_raw: bool) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(field_dir):
        rel_dir = Path(dirpath).relative_to(field_dir)
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
            and not (rel_dir == Path(".") and d == RAW_DIRNAME and not include_raw)
        )
        # `raw/` is in _SKIP_DIRS for indexing; pack wants it unless told not to.
        if (include_raw and rel_dir == Path(".") and (field_dir / RAW_DIRNAME).is_dir()
                and RAW_DIRNAME not in dirnames):
            dirnames.append(RAW_DIRNAME)
            dirnames.sort()
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            if name.endswith((SUFFIX, SUFFIX + SIDECAR_SUFFIX)):
                continue
            if name == DB_FILENAME and not include_index:
                continue
            if name.startswith(DB_FILENAME + "-"):
                continue  # sqlite -wal / -shm / -journal sidecars
            out.append(Path(dirpath) / name)
    return out


def default_archive_path(field_dir: Path) -> Path:
    return field_dir.parent / (field_dir.name + SUFFIX)


def pack_field(
    field_dir: Path,
    out: Path | None = None,
    include_index: bool = True,
    include_raw: bool = True,
) -> PackResult:
    field_dir = field_dir.resolve()
    out = (out or default_archive_path(field_dir)).resolve()
    members = _members(field_dir, include_index, include_raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in members:
            arcname = path.relative_to(field_dir).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    digest = sha256_file(out)
    sidecar = out.with_name(out.name + SIDECAR_SUFFIX)
    sidecar.write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    return PackResult(path=out, sha256=digest, files=len(members), bytes=out.stat().st_size)


def _read_sidecar(zip_path: Path) -> str | None:
    sidecar = zip_path.with_name(zip_path.name + SIDECAR_SUFFIX)
    if not sidecar.exists():
        return None
    first = sidecar.read_text(encoding="utf-8").split()
    return first[0].lower() if first else None


def _safe_relative(name: str) -> PurePosixPath:
    p = PurePosixPath(name)
    if p.is_absolute() or any(part in ("..", "") for part in p.parts) or name.startswith("/"):
        raise UnpackError(f"refusing archive member {name!r}: path escapes the destination")
    return p


def default_dest(zip_path: Path) -> Path:
    name = zip_path.name
    if name.endswith(SUFFIX):
        name = name[: -len(SUFFIX)]
    elif name.endswith(".zip"):
        name = name[:-4]
    return Path.cwd() / name


def unpack_field(
    zip_path: Path,
    dest: Path | None = None,
    expected_sha256: str | None = None,
    force: bool = False,
) -> UnpackResult:
    zip_path = zip_path.resolve()
    dest = (dest or default_dest(zip_path)).resolve()
    digest = sha256_file(zip_path)

    expected = (expected_sha256 or _read_sidecar(zip_path) or "").lower() or None
    verified: bool | None = None
    if expected is not None:
        if expected != digest:
            raise PackVerifyError(
                f"{zip_path.name}: sha256 {digest[:12]}... does not match expected {expected[:12]}..."
            )
        verified = True

    if dest.exists() and any(dest.iterdir()) and not force:
        raise UnpackError(f"{dest} is not empty; pass --force to extract into it anyway")

    with zipfile.ZipFile(zip_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        rels = [_safe_relative(i.filename) for i in infos]
        # A folder zipped whole puts everything under one directory.
        tops = {r.parts[0] for r in rels}
        stripped = ""
        if len(tops) == 1 and all(len(r.parts) > 1 for r in rels):
            stripped = tops.pop()
            rels = [PurePosixPath(*r.parts[1:]) for r in rels]
        dest.mkdir(parents=True, exist_ok=True)
        for info, rel in zip(infos, rels):
            target = dest / Path(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src:
                target.write_bytes(src.read())

    result = UnpackResult(dest=dest, sha256=digest, verified=verified, files=len(infos), stripped_prefix=stripped)
    if (dest / DB_FILENAME).exists():
        result.has_index = True
        try:
            conn = db.open_field(dest)
        except db.SchemaVersionError as e:
            result.index_error = str(e)
            result.notes.append("packed index is unusable by this mf; delete it, then `mf init` and `mf index`")
        else:
            try:
                for filename, sha in conn.execute("SELECT filename, sha256 FROM pages").fetchall():
                    page = dest / filename
                    if not page.exists() or sha256_file(page) != sha:
                        result.index_drift += 1
            finally:
                conn.close()
            if result.index_drift:
                result.notes.append(f"{result.index_drift} page(s) differ from the packed index; run `mf index`")
    else:
        result.notes.append("no index in archive; run `mf init` then `mf index` to search it")
    return result
