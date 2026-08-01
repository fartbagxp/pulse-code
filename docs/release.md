# Releasing

Releases are cut by pushing a tag. `publish.yml` (single workflow, one run
per tag) handles the rest as three sequential jobs:

1. Bump `version` in `pyproject.toml`, commit it.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. **`build`** builds the sdist/wheel, failing fast if the tag doesn't match
   `pyproject.toml`'s version.
4. **`release`** (needs `build`) creates the GitHub Release with the built
   artifacts attached, the source of truth for what shipped.
5. **`publish`** (needs `release`) publishes those same artifacts to PyPI
   (`pulse-code`) via trusted publishing (OIDC) against the `prod`
   environment, with no API tokens stored in the repo.

The `needs:` chain means a failure at any step blocks everything after it.
For example, a PyPI hiccup can't leave a GitHub Release around for a package that
isn't actually installable. If the `publish` job fails after `release`
succeeds, use "Re-run failed jobs" on that workflow run rather than
re-tagging. PyPI publishing is immutable: once a version is published it
can't be re-uploaded, so a bad release means bumping to a new version.
