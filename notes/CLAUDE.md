# notes/ — mf's own operational memoryfield

This directory is a real `mf` field (`mf.sqlite3` at its root), separate
from the parent repo's source and from `../eval/corpus` (calibration
fixtures, not real memory). It gives `mf consolidate --plan` genuine
`raw/` data to run against, instead of only synthetic fixtures.

Before exploring the parent repo, run `mf search "<question>" --field .`.
Before finishing, write what you learned as a page with `mf write`, or stage it with `mf raw add`.
