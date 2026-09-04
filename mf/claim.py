"""`mf claim` -- atomic conditional insert into the `claims` table.

Per PLAN.md's "Write" layer and ROADMAP.md 4.3: two writers racing to
create a page for the same topic should degrade to one create and one
update, not two pages. `claim slug` is the primitive that makes that
possible without a coordinator -- whichever writer's INSERT lands first
wins the slug, and the loser gets back the winner's identity so it can
look up the resulting page and `write --update` it instead.

Slug is the filename stem (ROADMAP.md 4.3's proposal, decided here):
that's the thing two writers actually collide on when they both title a
new page for the same topic without seeing each other's draft. See
mf.page.Page.slug.

SQLite serializes concurrent writers at the file level, so the
INSERT ... ON CONFLICT DO NOTHING below is atomic across processes, not
just within one connection: a second process's INSERT blocks until the
first commits, then sees the row already there.

Claims never expire on their own. A writer that crashes between `claim`
and `write` holds the slug until it (or whoever inherits its identity)
runs `claim --release`; `mf lint` reports claims with no page behind
them as `orphan-claim` so they get noticed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from sqlite3 import Connection


@dataclass
class ClaimResult:
    slug: str
    claimed: bool
    claimed_by: str
    claimed_at: str
    released: bool = False

    def as_dict(self) -> dict:
        d = {
            "slug": self.slug,
            "claimed": self.claimed,
            "claimed_by": self.claimed_by,
            "claimed_at": self.claimed_at,
        }
        if self.released:
            d["released"] = True
        return d


def claim_slug(conn: Connection, slug: str, claimed_by: str) -> ClaimResult:
    """Try to claim `slug` for `claimed_by`. Returns claimed=True if this
    call now holds it (either it won the race, or it already held it --
    re-claiming your own slug is a no-op, not an error). claimed=False
    means someone else got there first; `claimed_by`/`claimed_at` name
    who and when, so the caller can look that page up and update it
    instead of creating a duplicate.
    """
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO claims (slug, claimed_by, claimed_at) VALUES (?, ?, ?) "
        "ON CONFLICT(slug) DO NOTHING",
        (slug, claimed_by, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT claimed_by, claimed_at FROM claims WHERE slug = ?", (slug,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"claim for {slug!r} vanished between insert and read")
    return ClaimResult(slug=slug, claimed=(row[0] == claimed_by), claimed_by=row[0], claimed_at=row[1])


def release_slug(conn: Connection, slug: str, claimed_by: str) -> ClaimResult:
    """Drop `claimed_by`'s claim on `slug`. released=True if a row was
    removed. A claim held by someone else is left alone and reported
    (claimed=False, their identity), so a release can never steal.
    A slug nobody holds releases as a no-op.
    """
    row = conn.execute(
        "SELECT claimed_by, claimed_at FROM claims WHERE slug = ?", (slug,)
    ).fetchone()
    if row is None:
        return ClaimResult(slug=slug, claimed=False, claimed_by=claimed_by, claimed_at="", released=False)
    if row[0] != claimed_by:
        return ClaimResult(slug=slug, claimed=False, claimed_by=row[0], claimed_at=row[1], released=False)
    conn.execute("DELETE FROM claims WHERE slug = ? AND claimed_by = ?", (slug, claimed_by))
    conn.commit()
    return ClaimResult(slug=slug, claimed=False, claimed_by=claimed_by, claimed_at=row[1], released=True)
