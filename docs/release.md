# Releasing

Releases are cut entirely from GitHub Actions. There is no local tagging step.

1. Go to **Actions → Publish → Run workflow** on `main`.
2. Pick the semver level (`patch`, `minor`, or `major`).
3. Watch the run.

`publish.yml` is a single workflow with one run per release, made of four sequential jobs:

- `bump` runs `uv version --bump <level>` (updating `pyproject.toml` and `uv.lock`), runs the unit tests against the locked environment, then commits `chore(release): vX.Y.Z` to `main` and pushes the `vX.Y.Z` tag. It fails before pushing anything if the tests fail or the tag already exists.
- `build` needs `bump`. It checks out the new tag and builds the sdist and wheel.
- `release` needs `build`. It creates the GitHub Release with the built artifacts attached, which is the source of truth for what shipped.
- `publish` needs `release`. It publishes those same artifacts to PyPI as `pulse-code` via trusted publishing (OIDC) against the `prod` environment, so no API tokens are stored in the repo.

The bump commit and tag are pushed with the default `GITHUB_TOKEN`, which works because `main` is not protected. If branch protection or a ruleset is added to `main`, the workflow will need a GitHub App token (or a bypass for it) to push.

## When Something Fails

The `needs:` chain means a failure at any step blocks everything after it. A PyPI hiccup can't leave a GitHub Release sitting around for a package that isn't actually installable.

If `build`, `release`, or `publish` fails after `bump` succeeded, the version commit and tag are already on `main`. Use "Re-run failed jobs" on that same workflow run rather than starting a new one, which would bump to the next version. PyPI publishing is immutable: once a version is published it can't be re-uploaded, so a genuinely bad release means bumping to a new version.
