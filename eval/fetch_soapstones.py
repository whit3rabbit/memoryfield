"""Fetch the soapstones demo memoryfield, pinned by sha256.

Cal Paterson's `soapstones.memoryfield.zip` (95 pages written by many
agents, plus a spec vector index) is the interop fixture for
tests/test_interop_soapstones.py and the third blind eval domain. Its
page content carries no stated license, so it is downloaded on demand
into the gitignored eval/fixtures/ rather than committed. The digest is
pinned, as the article itself recommends for external fields: a
changed upstream file fails loudly instead of silently changing what
the tests measure.

Run: uv run python3 eval/fetch_soapstones.py
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://blobs.calpaterson.com/soapstones.memoryfield.zip"
SHA256 = "a875515b525eada2095ffefa271ddf9dff5ca11275559a910e08f623eae598dc"
DEST = Path(__file__).resolve().parent / "fixtures" / "soapstones.memoryfield.zip"


def main() -> int:
    if DEST.exists() and hashlib.sha256(DEST.read_bytes()).hexdigest() == SHA256:
        print(f"already present: {DEST}")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    # The blob host returns 403 to Python's default User-Agent; curl's is fine.
    req = urllib.request.Request(URL, headers={"User-Agent": "mf-fetch-soapstones/1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        print(f"sha256 mismatch: got {digest}, expected {SHA256}; not written", file=sys.stderr)
        return 1
    DEST.write_bytes(data)
    print(f"fetched {len(data)} bytes to {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
