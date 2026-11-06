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

After the tested candidate is approved and integrated into `main`, create the exact branch `release/vX.Y.Z` from that tested commit. The `push` to this branch starts publication; normal PR branches and creating a GitHub Release do not.

The workflow verifies the branch name against package metadata, builds and smoke-tests the wheel, publishes to PyPI through OIDC, then creates the matching GitHub Release. Do not push a release branch or manually dispatch a second publication as part of candidate preparation. Verify the installed version and a demo after publication. PyPI artifacts are immutable; a correction requires a new version.

Do not store a PyPI API token in GitHub secrets for this workflow.
