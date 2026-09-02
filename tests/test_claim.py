from mf import claim, db


def test_first_claim_wins(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    result = claim.claim_slug(conn, "code-deploy-rollback", "agent-a")
    assert result.claimed is True
    assert result.claimed_by == "agent-a"
    assert result.slug == "code-deploy-rollback"
    conn.close()


def test_second_claim_loses_and_sees_winner(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    first = claim.claim_slug(conn, "code-deploy-rollback", "agent-a")
    second = claim.claim_slug(conn, "code-deploy-rollback", "agent-b")

    assert second.claimed is False
    assert second.claimed_by == "agent-a"
    assert second.claimed_at == first.claimed_at
    conn.close()


def test_reclaiming_own_slug_is_a_noop_success(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    first = claim.claim_slug(conn, "code-deploy-rollback", "agent-a")
    again = claim.claim_slug(conn, "code-deploy-rollback", "agent-a")

    assert again.claimed is True
    assert again.claimed_at == first.claimed_at  # ON CONFLICT DO NOTHING: row unchanged
    conn.close()


def test_different_slugs_dont_collide(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    a = claim.claim_slug(conn, "code-deploy-rollback", "agent-a")
    b = claim.claim_slug(conn, "code-deploy-forward", "agent-b")

    assert a.claimed is True
    assert b.claimed is True
    conn.close()
