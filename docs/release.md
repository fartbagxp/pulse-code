# Releasing

Cutting a release takes three steps:

1. Bump `version` in `pyproject.toml` and commit it.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. Watch the run.

Pushing the tag starts `publish.yml`, a single workflow with one run per tag,
which does the rest as three sequential jobs:

- `build` builds the sdist and wheel, failing fast if the tag doesn't match
  the version in `pyproject.toml`.
- `release` needs `build`. It creates the GitHub Release with the built
  artifacts attached, which is the source of truth for what shipped.
- `publish` needs `release`. It publishes those same artifacts to PyPI as
  `pulse-code` via trusted publishing (OIDC) against the `prod` environment,
  so no API tokens are stored in the repo.

## When Something Fails

The `needs:` chain means a failure at any step blocks everything after it. A
PyPI hiccup can't leave a GitHub Release sitting around for a package that
isn't actually installable.

If `publish` fails after `release` succeeded, use "Re-run failed jobs" on that
workflow run rather than re-tagging. PyPI publishing is immutable: once a
version is published it can't be re-uploaded, so a genuinely bad release means
bumping to a new version.
