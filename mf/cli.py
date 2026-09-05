"""Command-line entry point for `mf`.

Every command is real: `init`/`index`/`search`/`read`/`write`/`claim`/
`consolidate --plan`/`lint`/`pack`/`unpack`/`import`/`hook`/`raw add`/
`model`/`mcp`/`setup` (ROADMAP.md 1.3-1.6, 2.1-2.4, 3.1-3.2, 4.2-4.3,
5.1, 5.3).

One place turns failures into exit codes: `main()` maps every error a
user can cause or fix (no field here, an old schema, a bad flag value,
a locked index, an unparsable page, a missing model) to a one-line
`mf <cmd>: ...` on stderr and exit 1. Commands keep their own codes for
outcomes that aren't errors: `write` 2 on a dedup block, `claim` 2 on a
lost race, `search` 3 on a stale index, `unpack` 2 on a digest
mismatch, `lint --check` 1 on findings, `setup install`/`uninstall` 1
when any file had to be skipped (unparsable JSON, a foreign skill dir,
a conflicting Codex table), bare `setup` 1 outside a terminal. Hooks
return 0 no matter what.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

from mf import __version__, db, embedder, importers, indexer, schema
from mf import claim as claim_mod
from mf import consolidate as consolidate_mod
from mf import harnesses as harnesses_mod
from mf import hooks as hooks_mod
from mf import lint as lint_mod
from mf import models as models_mod
from mf import pack as pack_mod
from mf import raw as raw_mod
from mf import read as read_mod
from mf import search as search_mod
from mf import setup as setup_mod
from mf import write as write_mod
from mf.page import PageParseError
from mf.schema import DEFAULT_MODEL_CODE

# Failures a one-line message serves better than a traceback.
_USER_ERRORS: tuple[type[BaseException], ...] = (
    db.FieldNotFoundError,
    db.SchemaVersionError,
    schema.EmbeddingDimMismatchError,
    embedder.UnknownModelCodeError,
    write_mod.WriteValidationError,
    raw_mod.EmptyRawTextError,
    read_mod.PageNotFoundError,
    read_mod.SectionNotFoundError,
    PageParseError,
    pack_mod.UnpackError,
    sqlite3.DatabaseError,
    zipfile.BadZipFile,
    OSError,
    ValueError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mf", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mf {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="create mf.sqlite3 in a field")
    init_parser.add_argument(
        "dir", nargs="?", default=None,
        help=f"field directory (default: {db.DEFAULT_FIELD_DIRNAME})",
    )
    init_parser.add_argument(
        "--model", choices=sorted(embedder.MODEL_REGISTRY), default=DEFAULT_MODEL_CODE,
        help="embedding model for this field; fixed at init (default: %(default)s)",
    )
    init_parser.add_argument(
        "--no-setup", action="store_true",
        help="create the index only; skip the harness wizard that runs on a terminal",
    )

    setup_parser = subparsers.add_parser(
        "setup", help="wire mf into a coding-agent harness (interactive with no subcommand)"
    )
    setup_sub = setup_parser.add_subparsers(dest="setup_command")
    for verb, help_text in (
        ("install", "write instructions, skill, MCP, and hooks for the chosen harnesses"),
        ("uninstall", "remove what `setup install` wrote, leaving everything else"),
    ):
        sp = setup_sub.add_parser(verb, help=help_text)
        sp.add_argument(
            "--harness", nargs="+", required=True, choices=harnesses_mod.MENU_ORDER,
            metavar="ID", help="one or more of: " + ", ".join(harnesses_mod.MENU_ORDER),
        )
        sp.add_argument("--instructions", action="store_true", help="the two-line block in CLAUDE.md/AGENTS.md")
        sp.add_argument("--skill", action="store_true", help="the mf skill directory")
        sp.add_argument("--mcp", action="store_true", help="an `mf mcp` server entry")
        sp.add_argument("--hooks", action="store_true", help="Stop and SessionEnd hooks (Claude Code)")
        sp.add_argument("--all-surfaces", action="store_true", help="every surface the harness supports")
        sp.add_argument("--field", default="notes", help="field directory relative to --root (default: %(default)s)")
        sp.add_argument("--root", default=".", help="project root (default: cwd)")
        sp.add_argument("--dry-run", action="store_true", help="list what would change, write nothing")
        sp.add_argument("--json", action="store_true", help="output JSON instead of text")
    sp = setup_sub.add_parser("status", help="show what is installed for each harness")
    sp.add_argument("--harness", nargs="+", choices=harnesses_mod.MENU_ORDER, metavar="ID", default=None)
    sp.add_argument("--field", default="notes", help="field directory relative to --root (default: %(default)s)")
    sp.add_argument("--root", default=".", help="project root (default: cwd)")
    sp.add_argument("--json", action="store_true", help="output JSON instead of text")
    sp = setup_sub.add_parser("prompt", help="print the prompt that has an agent seed the field")
    sp.add_argument("--field", default="notes", help="field directory (default: %(default)s)")
    sp.add_argument("--reference", default=None, help="path to the installed skill's reference.md")

    index_parser = subparsers.add_parser(
        "index", help="scan a field's pages into mf.sqlite3 (migrates a v2 index in place)"
    )
    index_parser.add_argument("dir", nargs="?", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")

    search_parser = subparsers.add_parser("search", help="search a field")
    search_parser.add_argument("query", help="the search query text")
    search_parser.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
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
    read_parser.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
    read_parser.add_argument("--tier", choices=read_mod.TIERS, default=None)
    read_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    write_parser = subparsers.add_parser("write", help="validate, dedup-check, and index a page")
    write_parser.add_argument(
        "path",
        help="draft page: a path outside the field (copied in on a pass), a path "
             "inside it (indexed in place), or '-' for stdin (needs --dest)",
    )
    write_parser.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
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
    claim_parser.add_argument("--release", action="store_true", help="drop your own claim on the slug")
    claim_parser.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
    claim_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    consolidate_parser = subparsers.add_parser(
        "consolidate", help="read raw/, propose create/review actions per entry (no writes)"
    )
    consolidate_parser.add_argument(
        "--plan", action="store_true", required=True,
        help="required: consolidate only plans so far, it doesn't execute",
    )
    consolidate_parser.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
    consolidate_parser.add_argument(
        "--threshold", type=float, default=consolidate_mod.REVIEW_THRESHOLD,
        help="cosine distance below which a candidate triggers review (default: %(default)s, untuned)",
    )
    consolidate_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    lint_parser = subparsers.add_parser("lint", help="check pages against the writing conventions")
    lint_parser.add_argument("dir", nargs="?", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
    lint_parser.add_argument("--check", action="store_true", help="exit 1 on any error or warning (CI)")
    lint_parser.add_argument("--all", action="store_true", help="also print info-level findings")
    lint_parser.add_argument("--json", action="store_true", help="output JSON instead of text")

    pack_parser = subparsers.add_parser("pack", help="archive a field as <name>.memoryfield.zip + .sha256")
    pack_parser.add_argument("dir", nargs="?", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
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
        sp.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
        sp.add_argument("--dry-run", action="store_true", help="list what would be written, write nothing")
        sp.add_argument("--json", action="store_true", help="output JSON instead of text")

    hook_parser = subparsers.add_parser("hook", help="Claude Code hook handlers (read the hook JSON on stdin)")
    hook_sub = hook_parser.add_subparsers(dest="hook_command")
    for name, help_text in (
        ("stop", "Stop hook: ask the agent to capture before finishing, once per session"),
        ("session-end", "SessionEnd hook: write a transcript pointer to raw/"),
    ):
        sp = hook_sub.add_parser(name, help=help_text)
        sp.add_argument(
            "--field", default=None,
            help="field directory relative to the hook payload's cwd (default: the cwd itself)",
        )

    raw_parser = subparsers.add_parser("raw", help="raw/ staging-area operations")
    raw_subparsers = raw_parser.add_subparsers(dest="raw_command")
    raw_add_parser = raw_subparsers.add_parser("add", help="append a session extract to raw/")
    raw_add_parser.add_argument(
        "text", nargs="?", default=None, help="text to append; reads stdin if omitted"
    )
    raw_add_parser.add_argument("--field", default=None, help="field directory (default: the cwd if it is a field, else ./notes)")
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

    mcp_parser = subparsers.add_parser(
        "mcp", help="run an MCP server wrapping search/read/write/raw_add (stdio transport)"
    )
    mcp_parser.add_argument(
        "--field", default=None,
        help="default field directory for every tool call (default: the cwd if it is a field, else ./notes)",
    )
    return parser


def _cmd_init(args: argparse.Namespace) -> int:
    entry = embedder.registry_entry(args.model)
    root = Path.cwd().resolve()
    if args.no_setup or not _on_a_terminal():
        field_dir = Path(args.dir or db.DEFAULT_FIELD_DIRNAME).resolve()
        try:
            db_path = db.init_field(field_dir, model_code=args.model, embedding_dim=entry["dim"])
        except db.FieldExistsError as e:
            sys.stderr.write(f"mf init: {e} already exists; nothing to do.\n")
            return 1
        print(f"Initialized empty field at {db_path} (model {args.model}, {entry['dim']}-d)")
        return 0

    from mf import wizard  # lazy: pulls questionary and prompt_toolkit

    if args.dir is not None:
        field_dir = Path(args.dir).resolve()
        try:
            db_path = db.init_field(field_dir, model_code=args.model, embedding_dim=entry["dim"])
        except db.FieldExistsError as e:
            sys.stderr.write(f"mf init: {e} already exists; nothing to do.\n")
            return 1
        print(f"Initialized empty field at {db_path} (model {args.model}, {entry['dim']}-d)")
        if field_dir != root and root not in field_dir.parents:
            print("Run `mf setup` from the project root to wire a coding agent to this field.")
            return 0
        rel = "." if field_dir == root else field_dir.relative_to(root).as_posix()
        return wizard.run_wizard(root, wizard.QuestionaryPrompter(), field=rel, model_code=args.model)

    return wizard.run_wizard(root, wizard.QuestionaryPrompter(), field=None, model_code=args.model, is_init=True)


def _on_a_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _cmd_setup(args: argparse.Namespace) -> int:
    sub = args.setup_command
    if sub is None:
        if not _on_a_terminal():
            sys.stderr.write(
                "mf setup: not a terminal; use `mf setup install --harness ... --field DIR` "
                "(see `mf setup install --help`)\n"
            )
            return 1
        from mf import wizard

        return wizard.run_wizard(Path.cwd().resolve(), wizard.QuestionaryPrompter())
    if sub == "prompt":
        print(setup_mod.seeding_prompt(args.field, args.reference), end="")
        return 0
    if sub == "status":
        result = setup_mod.status(Path(args.root), args.field, args.harness)
        print(json.dumps(result.as_dict(), indent=2) if args.json else setup_mod.render_status_text(result))
        return 0
    surfaces = {
        "instructions": args.instructions or args.all_surfaces,
        "skill": args.skill or args.all_surfaces,
        "mcp": args.mcp or args.all_surfaces,
        "hooks": args.hooks or args.all_surfaces,
    }
    if not any(surfaces.values()):
        sys.stderr.write(f"mf setup {sub}: pick at least one surface (--instructions, --skill, --mcp, --hooks, --all-surfaces)\n")
        return 1
    choices = setup_mod.SetupChoices(root=Path(args.root), field=args.field, harnesses=list(args.harness), **surfaces)
    run = setup_mod.install if sub == "install" else setup_mod.uninstall
    result = run(choices, dry_run=args.dry_run)
    print(json.dumps(result.as_dict(), indent=2) if args.json else setup_mod.render_setup_text(result))
    return 1 if result.failed else 0


def _cmd_index(args: argparse.Namespace) -> int:
    field_dir = db.resolve_field_dir(args.dir)
    migrated_from = db.migrate_field(field_dir)
    if migrated_from is not None:
        print(f"migrated index v{migrated_from} -> v{schema.SCHEMA_VERSION}")
    conn = db.open_field(field_dir)
    try:
        result = indexer.index_field(field_dir, conn)
    finally:
        conn.close()
    print(
        f"{len(result.upserted)} upserted, {result.unchanged} unchanged, "
        f"{len(result.deleted)} deleted"
    )
    for rel, why in result.skipped.items():
        sys.stderr.write(f"mf index: skipped {rel}: {why}\n")
    for uuid, rels in result.duplicates.items():
        sys.stderr.write(
            f"mf index: uuid {uuid!r} is claimed by {', '.join(rels)}; none of them "
            "was indexed, give all but one a new uuid\n"
        )
    return 1 if result.duplicates else 0


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
    field_dir = db.resolve_field_dir(args.field)
    conn = db.open_field(field_dir)
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
    field_dir = db.resolve_field_dir(args.field)
    conn = db.open_field(field_dir)
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
    field_dir = db.resolve_field_dir(args.field)
    if args.path == "-" and not args.dest:
        sys.stderr.write("mf write: reading from stdin needs --dest NAME\n")
        return 1
    conn = db.open_field(field_dir)
    try:
        if args.path == "-":
            result = write_mod.write_text(
                field_dir, conn, sys.stdin.read(), args.dest,
                update_uuid=args.update, force=args.force,
            )
        else:
            result = write_mod.write_page(
                field_dir, conn, Path(args.path),
                update_uuid=args.update, force=args.force, dest_name=args.dest,
            )
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_write_text(result))
    return 0 if result.written else 2


def _claim_age(claimed_at: str) -> str:
    from datetime import UTC, datetime
    try:
        then = datetime.fromisoformat(claimed_at)
    except ValueError:
        return ""
    hours = (datetime.now(UTC) - then).total_seconds() / 3600
    if hours < 1:
        return "under an hour ago"
    if hours < 48:
        return f"{hours:.0f} hours ago"
    return f"{hours / 24:.0f} days ago"


def _render_claim_text(result: claim_mod.ClaimResult) -> str:
    if result.released:
        return f"Released {result.slug!r} (was claimed by {result.claimed_by} at {result.claimed_at})"
    if result.claimed:
        return f"Claimed {result.slug!r} for {result.claimed_by} at {result.claimed_at}"
    if not result.claimed_at:
        return f"mf claim: {result.slug!r} was not claimed; nothing to release"
    age = _claim_age(result.claimed_at)
    age_note = f" ({age})" if age else ""
    return (
        f"mf claim: {result.slug!r} already claimed by {result.claimed_by} "
        f"at {result.claimed_at}{age_note}; look up that page and use `write --update` instead"
    )


def _cmd_claim(args: argparse.Namespace) -> int:
    field_dir = db.resolve_field_dir(args.field)
    conn = db.open_field(field_dir)
    try:
        if args.release:
            result = claim_mod.release_slug(conn, args.slug, args.by)
        else:
            result = claim_mod.claim_slug(conn, args.slug, args.by)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(_render_claim_text(result))
    if args.release:
        return 0 if (result.released or not result.claimed_at) else 2
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
    field_dir = db.resolve_field_dir(args.field)
    conn = db.open_field(field_dir)
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
    field_dir = db.resolve_field_dir(args.dir)
    conn = None
    try:
        conn = db.open_field(field_dir)
    except db.FieldNotFoundError:
        pass  # lint the pages alone; index-drift checks need mf init
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
    field_dir = db.resolve_field_dir(args.dir)
    if not field_dir.is_dir():
        sys.stderr.write(f"mf pack: {field_dir} is not a directory\n")
        return 1
    result = pack_mod.pack_field(
        field_dir, out=Path(args.out) if args.out else None,
        include_index=not args.no_index, include_raw=not args.no_raw, spec=args.spec,
    )
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
    field_dir = db.resolve_field_dir(args.field)
    src = Path(args.src)
    if not src.is_dir():
        sys.stderr.write(f"mf import: {src} is not a directory\n")
        return 1
    conn = db.open_field(field_dir)
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
    if args.hook_command not in ("stop", "session-end"):
        sys.stderr.write("mf hook: expected a subcommand (stop, session-end)\n")
        return 1
    # A hook must never surface a traceback inside Claude Code: report on
    # stderr, exit 0, and let the session go on.
    try:
        payload = hooks_mod.read_payload(sys.stdin)
        if args.hook_command == "stop":
            result = hooks_mod.stop(payload, field=args.field)
            if result.output is not None:
                print(json.dumps(result.output))
        else:
            hooks_mod.session_end(payload, field=args.field)  # fire-and-forget; stdout isn't shown
    except Exception as e:
        sys.stderr.write(f"mf hook {args.hook_command}: {type(e).__name__}: {e}\n")
    return 0


def _cmd_raw(args: argparse.Namespace) -> int:
    if args.raw_command != "add":
        sys.stderr.write("mf raw: expected a subcommand (add)\n")
        return 1
    field_dir = db.resolve_field_dir(args.field)
    db.open_field(field_dir).close()  # raw/ never touches the index; only used to validate the field exists

    text = args.text if args.text is not None else sys.stdin.read()
    result = raw_mod.add_raw(field_dir, text)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    elif result.written:
        print(f"Appended to {result.path}")
    else:
        print(f"Skipped: duplicate of {result.path}")
    return 0


def _size_str(size_mb: int) -> str:
    return f"~{size_mb} MB" if size_mb < 1000 else f"~{size_mb / 1000:.1f} GB"


def _render_model_list_text(models: list[models_mod.ModelInfo]) -> str:
    lines = [
        f"{'Model':<30} {'Dim':<6} {'Size':<10} {'Speed':<9} {'Cached':<8} {'Description'}",
        "-" * 105,
    ]
    for m in models:
        prefix = "* " if m.is_default else "  "
        name = prefix + m.model_code
        cached_str = "yes" if m.is_cached else "no"
        lines.append(
            f"{name:<30} {m.dim:<6} {_size_str(m.size_mb):<10} {m.speed:<9} {cached_str:<8} {m.description}"
        )
    lines.append("")
    lines.append("* = default model for `mf init`")
    return "\n".join(lines)


def _cmd_model(args: argparse.Namespace) -> int:
    if args.model_command == "list":
        models = models_mod.list_models()
        if args.json:
            print(json.dumps([m.as_dict() for m in models], indent=2))
        else:
            print(_render_model_list_text(models))
        return 0
    if args.model_command == "install":
        try:
            result = models_mod.install_model(args.name)
        except Exception as e:
            sys.stderr.write(f"mf model install: failed to install {args.name}: {e}\n")
            return 1
        if args.json:
            print(json.dumps(result.as_dict(), indent=2))
        elif result.already_cached:
            print(f"Model {result.model_code} is already downloaded and ready ({result.dim}-d, {_size_str(result.size_mb)}).")
        else:
            print(f"Downloaded and ready: {result.model_code} ({result.dim}-d, {_size_str(result.size_mb)}).")
        return 0
    sys.stderr.write("mf model: expected a subcommand (list, install)\n")
    return 1


def _cmd_mcp(args: argparse.Namespace) -> int:
    try:
        from mf import mcp_server  # lazy: the server stack loads only for `mf mcp`
    except ImportError:
        sys.stderr.write(
            "mf mcp: the mcp package isn't importable; reinstall with "
            "`uv tool install --force memoryfield` (or `pipx reinstall memoryfield`) and retry\n"
        )
        return 1

    mcp_server.main(field=str(db.resolve_field_dir(args.field)))
    return 0


_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init": _cmd_init,
    "index": _cmd_index,
    "search": _cmd_search,
    "read": _cmd_read,
    "write": _cmd_write,
    "claim": _cmd_claim,
    "consolidate": _cmd_consolidate,
    "lint": _cmd_lint,
    "pack": _cmd_pack,
    "unpack": _cmd_unpack,
    "import": _cmd_import,
    "hook": _cmd_hook,
    "raw": _cmd_raw,
    "model": _cmd_model,
    "mcp": _cmd_mcp,
    "setup": _cmd_setup,
}


def _label(args: argparse.Namespace) -> str:
    parts = [args.command]
    for attr in ("raw_command", "model_command", "hook_command", "setup_command"):
        value = getattr(args, attr, None)
        if value:
            parts.append(value)
    return "mf " + " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return _COMMANDS[args.command](args)
    except KeyboardInterrupt:
        return 130
    except _USER_ERRORS as e:
        sys.stderr.write(f"{_label(args)}: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
