## What and why

<!-- What changes, and the problem or evidence behind it. Link issues. -->

## Test evidence

<!-- What you ran and what it showed. Paste the summary line of scripts/check.sh. For a change to the
reading or validation logic, say which test fails without it. -->

- [ ] `scripts/check.sh` passes locally (ruff, ruff format, card syntax, pytest)
- [ ] New behaviour has a test; a bug fix has a regression test
- [ ] Validator changes keep `tests/test_field_corpus.py` passing

## Release impact

<!-- Merging to main releases automatically when manifest.json has a new version. -->

- [ ] No release: `manifest.json` version unchanged
- [ ] Releases `vX.Y.Z`: version bumped in `manifest.json`, `CHANGELOG.md` section added
- [ ] Changes what users see or must do (state class, entity IDs, options, setup): described in `CHANGELOG.md`
