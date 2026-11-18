# Contributing

Thanks for helping. Issues and pull requests are welcome; for anything larger than a fix, open an issue
first so we can agree on the approach.

## Pull requests

`main` is protected: every change goes through a pull request, squash-merged, with these checks green
and the branch up to date with `main`:

- **Lint and tests**: `scripts/check.sh` (ruff, ruff format, card syntax, pytest on a real Home Assistant core)
- **Hassfest**: Home Assistant's integration validation
- **HACS validation**

The repository owner reviews and merges every pull request (`.github/CODEOWNERS`). The pull request
template asks for what and why, test evidence and the release impact.

## Running the checks

```bash
python3.13 -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt
scripts/check.sh                 # everything CI runs
scripts/check.sh -k validator    # extra arguments go to pytest
```

- New behaviour needs a test; a bug fix needs a regression test that fails without the fix.
- The reading and validation logic lives in `reading.py` and `validator.py` (pure Python). Any change to
  `validator.py` must keep `tests/test_field_corpus.py` passing: it replays two real days of a glitching
  camera. [`docs/prior-art.md`](docs/prior-art.md) records why each rule exists.
- New user-facing strings go in both `translations/en.json` and `it.json` (a test compares them).
- [`CLAUDE.md`](CLAUDE.md) has the layout of the code and the rules that keep it maintainable.

## How releases happen

The version lives only in `custom_components/meter_vision/manifest.json`. When a pull request that bumps it
is merged, the `Release` job of `.github/workflows/validate.yml` waits for all checks, then creates the tag
`vX.Y.Z` and the GitHub release, with the matching `CHANGELOG.md` section as the notes. **Merging a version
bump is the release.** Tags are immutable once created. HACS picks up the new release by itself.

## Licence

Meter Vision is GPL-3.0-or-later, a fork of [ha-ai-meter-reader](https://github.com/artech-lab/ha-ai-meter-reader).
By contributing you agree that your contribution is licensed the same way. New source files start with
`# SPDX-License-Identifier: GPL-3.0-or-later`.
