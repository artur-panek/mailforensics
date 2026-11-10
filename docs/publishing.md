# Publishing to PyPI

MailForensics is prepared for secretless PyPI publishing with GitHub Actions Trusted Publishing.

## One-time setup

Create a **pending publisher** in your PyPI account with exactly these values:

- PyPI project name: `mailforensics`
- GitHub owner: `artur-panek`
- GitHub repository: `mailforensics`
- Workflow filename: `publish-to-pypi.yml`
- Environment name: `pypi`

Official guide: https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/

For stronger release protection, configure the GitHub `pypi` environment with required reviewers before publishing.

## Local release validation

```bash
python -m pip install --upgrade build twine
rm -rf dist build
python -m build
python -m twine check --strict dist/*
```

Smoke-test the built wheel:

```bash
python -m venv /tmp/mailforensics-release
/tmp/mailforensics-release/bin/python -m pip install dist/*.whl
/tmp/mailforensics-release/bin/mailforensics --version
/tmp/mailforensics-release/bin/mailforensics demo delivered --color never --ascii
```

## Releases

For each public release:

1. Update the version in `pyproject.toml` and `src/mailforensics/__init__.py`, and add the dated release entry to `CHANGELOG.md`.
2. Merge the release-ready PR into `main` after CI passes.
3. Create and push a branch named `release/vX.Y.Z` at the tested merge commit. Pushing this branch starts publication; merging into `main` or creating a tag alone does not.
4. The workflow verifies that the release branch matches the package version, builds a fresh sdist and wheel, validates metadata, and smoke-tests the wheel.
5. The `pypi` job obtains a short-lived OIDC credential and publishes the distributions to PyPI.
6. After PyPI publishing succeeds, the workflow creates the GitHub Release tagged `vX.Y.Z` at the release commit.
7. Verify the published version from a clean environment:

```bash
python -m pip install "mailforensics==X.Y.Z"
mailforensics --version
mailforensics demo
```

Do not store a PyPI API token in GitHub secrets for this workflow.
