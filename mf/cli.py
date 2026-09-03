"""Command-line entry point for `mf`.

Every Phase 1-3 command is real: `init`/`index`/`search`/`read`/
`write`/`raw add`/`lint`/`pack`/`unpack`/`hook`/`import` (ROADMAP.md
1.3-1.6, 2.1-2.4, 3.1-3.2). `claim` (ROADMAP.md 4.3) is the first
Phase 4 command.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from mf import __version__, db, embedder, importers, indexer
from mf import claim as claim_mod
from mf import consolidate as consolidate_mod
from mf import hooks as hooks_mod
from mf import lint as lint_mod
from mf import models as models_mod
from mf import pack as pack_mod
from mf import raw as raw_mod
from mf import read as read_mod
from mf import search as search_mod
from mf import write as write_mod
from mf.page import PageParseError
from mf.schema import DEFAULT_MODEL_CODE

STUB_COMMANDS = ()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mf", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mf {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="create mf.sqlite3 in a field")
    init_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")
    init_parser.add_argument(
        "--model", choices=sorted(embedder.MODEL_REGISTRY), default=DEFAULT_MODEL_CODE,
        help="embedding model for this field; fixed at init (default: %(default)s)",
    )

    index_parser = subparsers.add_parser("index", help="scan a field's pages into mf.sqlite3")
    index_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")

    search_parser = subparsers.add_parser("search", help="search a field")
    search_parser.add_argument("query", help="the search query text")
    search_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    search_parser.add_argument("--limit", type=int, default=search_mod.DEFAULT_LIMIT)
    search_parser.add_argument(
        "--neighbor-limit", type=int, default=search_mod.DEFAULT_NEIGHBOR_LIMIT
    )
    search_parser.add_argument("--budget", type=int, default=None, help="token cap on the result set")
    search_parser.add_argument(
        "--stale-ok", action="store_true",
        help="return results whose page changed on disk since `mf index` (marked stale) instead of refusing",
    )
    search_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    read_parser = subparsers.add_parser("read", help="read a page's L1/L2 slice or a #section")
    read_parser.add_argument("refs", nargs="+", help="uuid or uuid#section, one or more")
    read_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    read_parser.add_argument("--tier", choices=read_mod.TIERS, default=None)
    read_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    write_parser = subparsers.add_parser("write", help="validate, dedup-check, and index a page")
    write_parser.add_argument(
        "path",
        help="draft page: a path outside the field (copied in on a pass), a path "
             "inside it (indexed in place), or '-' for stdin (needs --dest)",
    )
    write_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    write_parser.add_argument(
        "--dest", metavar="NAME", default=None,
        help="filename inside the field to write the draft to (default: the draft's own name)",
    )
    write_parser.add_argument(
        "--update", metavar="UUID", default=None,
        help="uuid this write intentionally updates (skips the dedup gate)",
    )
    write_parser.add_argument("--force", action="store_true", help="skip the dedup gate")
    write_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    claim_parser = subparsers.add_parser(
        "claim", help="atomically claim a page slug before creating it (multi-writer)"
    )
    claim_parser.add_argument("slug", help="the slug to claim (a page's filename stem)")
    claim_parser.add_argument("--by", required=True, metavar="WRITER", help="claimant identity")
    claim_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    claim_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    consolidate_parser = subparsers.add_parser(
        "consolidate", help="read raw/, propose create/review actions per entry (no writes)"
    )
    consolidate_parser.add_argument(
        "--plan", action="store_true", required=True,
        help="required: consolidate only plans so far, it doesn't execute",
    )
    consolidate_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    consolidate_parser.add_argument(
        "--threshold", type=float, default=consolidate_mod.REVIEW_THRESHOLD,
        help="cosine distance below which a candidate triggers review (default: %(default)s, untuned)",
    )
    consolidate_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    lint_parser = subparsers.add_parser("lint", help="check pages against the writing conventions")
    lint_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")
    lint_parser.add_argument("--check", action="store_true", help="exit 1 on any error or warning (CI)")
    lint_parser.add_argument("--all", action="store_true", help="also print info-level findings")
    lint_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    pack_parser = subparsers.add_parser("pack", help="archive a field as <name>.memoryfield.zip + .sha256")
    pack_parser.add_argument("dir", nargs="?", default=".", help="field directory (default: cwd)")
    pack_parser.add_argument("--out", default=None, help="archive path (default: ../<field name>.memoryfield.zip)")
    pack_parser.add_argument("--no-index", action="store_true", help="leave mf.sqlite3 out")
    pack_parser.add_argument("--no-raw", action="store_true", help="leave raw/ out")
    pack_parser.add_argument("--spec", action="store_true",
                             help="spec-only archive for other readers: root-level pages, no mf.sqlite3 or raw/, "
                                  "plus a <model>.sqlite3 index in the spec's schema")
    pack_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    unpack_parser = subparsers.add_parser("unpack", help="verify and extract a .memoryfield.zip")
    unpack_parser.add_argument("zip", help="archive path")
    unpack_parser.add_argument("dest", nargs="?", default=None, help="destination directory (default: ./<name>)")
    unpack_parser.add_argument("--sha256", default=None, help="expected digest (default: the .sha256 sidecar, if present)")
    unpack_parser.add_argument("--force", action="store_true", help="extract into a non-empty destination")
    unpack_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    import_parser = subparsers.add_parser("import", help="import an existing note collection as pages")
    import_sub = import_parser.add_subparsers(dest="import_kind")
    for kind, help_text in (
        ("claude-memory", "a Claude Code auto-memory directory (MEMORY.md + topic files)"),
        ("wiki", "a Karpathy-style wiki (index.md + pages, subdirs flattened)"),
    ):
        sp = import_sub.add_parser(kind, help=help_text)
        sp.add_argument("src", help="source directory")
        sp.add_argument("--field", default=".", help="field directory (default: cwd)")
        sp.add_argument("--dry-run", action="store_true", help="list what would be written, write nothing")
        sp.add_argument("--json", action="store_true", help="output JSON instead of text")

    hook_parser = subparsers.add_parser("hook", help="Claude Code hook handlers (read the hook JSON on stdin)")
    hook_sub = hook_parser.add_subparsers(dest="hook_command")
    hook_sub.add_parser("stop", help="Stop hook: ask the agent to capture before finishing, once per session")
    hook_sub.add_parser("session-end", help="SessionEnd hook: write a transcript pointer to raw/")

    raw_parser = subparsers.add_parser("raw", help="raw/ staging-area operations")
    raw_subparsers = raw_parser.add_subparsers(dest="raw_command")
    raw_add_parser = raw_subparsers.add_parser("add", help="append a session extract to raw/")
    raw_add_parser.add_argument(
        "text", nargs="?", default=None, help="text to append; reads stdin if omitted"
    )
    raw_add_parser.add_argument("--field", default=".", help="field directory (default: cwd)")
    raw_add_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    model_parser = subparsers.add_parser("model", help="list or download embedding models")
    model_sub = model_parser.add_subparsers(dest="model_command")

    model_list_parser = model_sub.add_parser("list", help="list available embedding models")
    model_list_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    model_install_parser = model_sub.add_parser("install", help="download and cache an embedding model")
    model_install_parser.add_argument(
        "name", choices=sorted(embedder.MODEL_REGISTRY), help="model name to install"
    )
    model_install_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    subparsers.add_parser(
        "mcp", help="run an MCP server wrapping search/read/write/raw_add (stdio transport)"
    )

    for name in STUB_COMMANDS:
        subparsers.add_parser(name)
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    field_dir = Path(args.dir).resolve()
    entry = embedder.registry_entry(args.model)
    try:
        db_path = db.init_field(field_dir, model_code=args.model, embedding_dim=entry["dim"])
    except db.FieldExistsError as e:
        sys.stderr.write(f"mf init: {e} already exists; nothing to do.\n")
        return 1
    print(f"Initialized empty field at {db_path} (model {args.model}, {entry['dim']}-d)")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    field_dir = Path(args.dir).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf index: {e}\n")
        return 1
    try:
        result = indexer.index_field(field_dir, conn)
    finally:
        conn.close()
    print(
        f"{len(result.upserted)} upserted, {result.unchanged} unchanged, "
        f"{len(result.deleted)} deleted"
    )
    return 0


def _render_stub_text(stub: search_mod.Stub, indent: str = "") -> str:
    head = f"{indent}- [{stub.uuid}] {stub.title}"
    if stub.stale:
        head += " (stale)"
    lines = [head]
    if stub.summary:
        lines.append(f"{indent}    {stub.summary}")
    if stub.status != "active":
        lines.append(f"{indent}    status: {stub.status}")
    if stub.supersedes:
        lines.append(f"{indent}    supersedes: {', '.join(stub.supersedes)}")
    for neighbor in stub.neighbors:
        lines.append(_render_stub_text(neighbor, indent + "    "))
    return "\n".join(lines)


def _render_text(result: search_mod.SearchResult) -> str:
    lines = [f"confidence: {result.confidence}"]
    if not result.results:
        lines.append("(no results)")
    for stub in result.results:
        lines.append(_render_stub_text(stub))
    return "\n".join(lines)


def _cmd_search(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf search: {e}\n")
        return 1
    try:
        result = search_mod.search(
            conn, args.query, limit=args.limit,
            neighbor_limit=args.neighbor_limit, budget=args.budget,
            field_dir=field_dir, stale_ok=args.stale_ok,
        )
    except search_mod.StaleIndexError as e:
        sys.stderr.write(f"mf search: {e}\n")
        return 3
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_text(result))
    return 0


def _render_read_text(results: list[read_mod.ReadResult]) -> str:
    lines = []
    for r in results:
        ref = f"{r.uuid}#{r.section}" if r.section else f"{r.uuid} ({r.tier})"
        lines.append(f"[{ref}] {r.title}")
        lines.append(r.body)
        if r is not results[-1]:
            lines.append("")
    return "\n".join(lines)


def _cmd_read(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf read: {e}\n")
        return 1
    try:
        results = read_mod.read(conn, args.refs, tier=args.tier, field_dir=field_dir)
    except (read_mod.PageNotFoundError, read_mod.SectionNotFoundError) as e:
        sys.stderr.write(f"mf read: not found: {e}\n")
        return 1
    finally:
        conn.close()

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        print(_render_read_text(results))
    return 0


def _render_write_text(result: write_mod.WriteResult) -> str:
    if result.written:
        return f"Wrote {result.uuid} to {result.path}"
    lines = [
        f"mf write: {len(result.duplicates)} possible near-duplicate(s) found; not written.",
    ]
    for d in result.duplicates:
        lines.append(f"  - [{d.uuid}] {d.title} (distance {d.distance:.3f})")
        lines.append(f"      {d.summary}")
    lines.append("Use --update <uuid> to update an existing page, or --force to write anyway.")
    if result.warning:
        lines.append(f"warning: {result.warning}")
    return "\n".join(lines)


def _cmd_write(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf write: {e}\n")
        return 1
    try:
        if args.path == "-":
            if not args.dest:
                sys.stderr.write("mf write: reading from stdin needs --dest NAME\n")
                return 1
            result = write_mod.write_text(
                field_dir, conn, sys.stdin.read(), args.dest,
                update_uuid=args.update, force=args.force,
            )
        else:
            result = write_mod.write_page(
                field_dir, conn, Path(args.path),
                update_uuid=args.update, force=args.force, dest_name=args.dest,
            )
    except (write_mod.WriteValidationError, PageParseError) as e:
        sys.stderr.write(f"mf write: {e}\n")
        return 1
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_write_text(result))
    return 0 if result.written else 2


def _render_claim_text(result: claim_mod.ClaimResult) -> str:
    if result.claimed:
        return f"Claimed {result.slug!r} for {result.claimed_by} at {result.claimed_at}"
    return (
        f"mf claim: {result.slug!r} already claimed by {result.claimed_by} "
        f"at {result.claimed_at}; look up that page and use `write --update` instead"
    )


def _cmd_claim(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf claim: {e}\n")
        return 1
    try:
        result = claim_mod.claim_slug(conn, args.slug, args.by)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_claim_text(result))
    return 0 if result.claimed else 2


def _render_consolidate_text(result: consolidate_mod.ConsolidatePlan) -> str:
    if not result.actions:
        return "(raw/ is empty; nothing to consolidate)"
    lines = []
    for a in result.actions:
        preview = a.text.splitlines()[0][:80] if a.text else ""
        lines.append(f"[{a.action}] {a.entry}: {preview}")
        for c in a.candidates:
            lines.append(f"    - [{c.uuid}] {c.title} (distance {c.distance:.3f})")
    return "\n".join(lines)


def _cmd_consolidate(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf consolidate: {e}\n")
        return 1
    try:
        result = consolidate_mod.plan(field_dir, conn, threshold=args.threshold)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_consolidate_text(result))
    return 0


def _render_lint_text(result: lint_mod.LintResult, show_all: bool) -> str:
    lines = []
    for f in result.findings:
        if f.severity == "info" and not show_all:
            continue
        where = f"{f.filename} [{f.uuid}]" if f.uuid else f.filename
        lines.append(f"{f.severity}: {f.code}: {where}: {f.message}")
    hidden = "" if show_all else " (--all to show info)"
    lines.append(
        f"{result.pages} pages: {result.count('error')} errors, "
        f"{result.count('warning')} warnings, {result.count('info')} info{hidden}"
    )
    return "\n".join(lines)


def _cmd_lint(args: argparse.Namespace) -> int:
    field_dir = Path(args.dir).resolve()
    conn = None
    try:
        conn = db.open_field(field_dir)
    except db.FieldNotFoundError:
        pass  # lint the pages alone; index-drift checks need mf init
    except db.SchemaVersionError as e:
        sys.stderr.write(f"mf lint: {e}\n")
        return 1
    try:
        result = lint_mod.lint_field(field_dir, conn)
    finally:
        if conn is not None:
            conn.close()
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_lint_text(result, args.all))
    return 1 if (args.check and result.failed) else 0


def _cmd_pack(args: argparse.Namespace) -> int:
    field_dir = Path(args.dir).resolve()
    if not field_dir.is_dir():
        sys.stderr.write(f"mf pack: {field_dir} is not a directory\n")
        return 1
    try:
        result = pack_mod.pack_field(
            field_dir, out=Path(args.out) if args.out else None,
            include_index=not args.no_index, include_raw=not args.no_raw, spec=args.spec,
        )
    except db.SchemaVersionError as e:
        sys.stderr.write(f"mf pack: {e}\n")
        return 1
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(f"Packed {result.files} files ({result.bytes} bytes) to {result.path}")
        print(f"sha256 {result.sha256} (sidecar {result.path.name}{pack_mod.SIDECAR_SUFFIX})")
        if result.spec_index:
            print(f"spec vector index {result.spec_index}")
        for rel in result.skipped:
            print(f"skipped {rel}: spec readers only see root-level [a-z0-9-] pages")
    return 0


def _cmd_unpack(args: argparse.Namespace) -> int:
    try:
        result = pack_mod.unpack_field(
            Path(args.zip), dest=Path(args.dest) if args.dest else None,
            expected_sha256=args.sha256, force=args.force,
        )
    except pack_mod.PackVerifyError as e:
        sys.stderr.write(f"mf unpack: {e}\n")
        return 2
    except (pack_mod.UnpackError, FileNotFoundError, zipfile.BadZipFile) as e:
        sys.stderr.write(f"mf unpack: {e}\n")
        return 1
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        v = "verified" if result.verified else "not verified (no sidecar, no --sha256)"
        print(f"Unpacked {result.files} files to {result.dest}; sha256 {result.sha256[:12]}... {v}")
        if result.stripped_prefix:
            print(f"stripped top-level directory {result.stripped_prefix!r}")
        for note in result.notes:
            print(f"note: {note}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    if args.import_kind not in ("claude-memory", "wiki"):
        sys.stderr.write("mf import: expected a kind (claude-memory, wiki)\n")
        return 1
    field_dir = Path(args.field).resolve()
    src = Path(args.src)
    if not src.is_dir():
        sys.stderr.write(f"mf import: {src} is not a directory\n")
        return 1
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf import: {e}\n")
        return 1
    try:
        fn = importers.import_claude_memory if args.import_kind == "claude-memory" else importers.import_wiki
        result = fn(src, field_dir, conn, dry_run=args.dry_run)
    finally:
        conn.close()
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        verb = "Would write" if result.dry_run else "Wrote"
        print(f"{verb} {len(result.pages)} page(s) from {src} ({result.kind})")
        for p in result.pages:
            print(f"  {p.dest}  [{p.uuid}] {p.title}")
        for s in result.skipped:
            print(f"  skipped: {s}")
        if not result.dry_run:
            print(f"indexed {result.indexed} page(s); run `mf lint {field_dir}` next")
    return 0


def _cmd_hook(args: argparse.Namespace) -> int:
    payload = hooks_mod.read_payload(sys.stdin)
    if args.hook_command == "stop":
        result = hooks_mod.stop(payload)
        if result.output is not None:
            print(json.dumps(result.output))
        return 0
    if args.hook_command == "session-end":
        hooks_mod.session_end(payload)  # fire-and-forget; stdout isn't shown
        return 0
    sys.stderr.write("mf hook: expected a subcommand (stop, session-end)\n")
    return 1


def _cmd_raw_add(args: argparse.Namespace) -> int:
    field_dir = Path(args.field).resolve()
    try:
        conn = db.open_field(field_dir)
    except (db.FieldNotFoundError, db.SchemaVersionError) as e:
        sys.stderr.write(f"mf raw add: {e}\n")
        return 1
    conn.close()  # raw/ never touches the index; only used to validate the field exists

    text = args.text if args.text is not None else sys.stdin.read()
    try:
        result = raw_mod.add_raw(field_dir, text)
    except raw_mod.EmptyRawTextError as e:
        sys.stderr.write(f"mf raw add: {e}\n")
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    elif result.written:
        print(f"Appended to {result.path}")
    else:
        print(f"Skipped: duplicate of {result.path}")
    return 0


def _render_model_list_text(models: list[models_mod.ModelInfo]) -> str:
    lines = [
        f"{'Model':<30} {'Dim':<6} {'Size':<10} {'Speed':<9} {'Cached':<8} {'Description'}",
        "-" * 105,
    ]
    for m in models:
        prefix = "* " if m.is_default else "  "
        name = prefix + m.model_code
        cached_str = "yes" if m.is_cached else "no"
        size_str = f"~{m.size_mb} MB" if m.size_mb < 1000 else f"~{m.size_mb / 1000:.1f} GB"
        lines.append(
            f"{name:<30} {m.dim:<6} {size_str:<10} {m.speed:<9} {cached_str:<8} {m.description}"
        )
    lines.append("")
    lines.append("* = default model for `mf init`")
    return "\n".join(lines)


def _cmd_model_list(args: argparse.Namespace) -> int:
    models = models_mod.list_models()
    if args.json:
        print(json.dumps([m.as_dict() for m in models], indent=2))
    else:
        print(_render_model_list_text(models))
    return 0


def _cmd_model_install(args: argparse.Namespace) -> int:
    try:
        result = models_mod.install_model(args.name)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"mf model install: failed to install {args.name}: {e}\n")
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        size_str = f"~{result.size_mb} MB" if result.size_mb < 1000 else f"~{result.size_mb / 1000:.1f} GB"
        if result.already_cached:
            print(f"Model {result.model_code} is already downloaded and ready ({result.dim}-d, {size_str}).")
        else:
            print(f"Downloaded and ready: {result.model_code} ({result.dim}-d, {size_str}).")
    return 0


def _cmd_mcp(args: argparse.Namespace) -> int:
    try:
        from mf import mcp_server  # lazy: mcp is an optional extra
    except ImportError:
        sys.stderr.write(
            "mf mcp: the mcp package isn't installed; run "
            "`uv tool install '.[mcp]'` (or `pip install 'mf[mcp]'`) and retry\n"
        )
        return 1

    mcp_server.main()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "index":
        return _cmd_index(args)
    if args.command == "search":
        return _cmd_search(args)
    if args.command == "read":
        return _cmd_read(args)
    if args.command == "write":
        return _cmd_write(args)
    if args.command == "claim":
        return _cmd_claim(args)
    if args.command == "consolidate":
        return _cmd_consolidate(args)
    if args.command == "lint":
        return _cmd_lint(args)
    if args.command == "pack":
        return _cmd_pack(args)
    if args.command == "unpack":
        return _cmd_unpack(args)
    if args.command == "import":
        return _cmd_import(args)
    if args.command == "hook":
        return _cmd_hook(args)
    if args.command == "mcp":
        return _cmd_mcp(args)
    if args.command == "raw":
        if args.raw_command == "add":
            return _cmd_raw_add(args)
        sys.stderr.write("mf raw: expected a subcommand (add)\n")
        return 1
    if args.command == "model":
        if args.model_command in ("list", "ls"):
            return _cmd_model_list(args)
        if args.model_command in ("install", "download", "pull"):
            return _cmd_model_install(args)
        sys.stderr.write("mf model: expected a subcommand (list, install)\n")
        return 1
    sys.stderr.write(
        f"mf {args.command}: not implemented yet — see ROADMAP.md Phase 1/2.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
