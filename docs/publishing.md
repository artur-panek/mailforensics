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

## First public release

After the pending publisher exists and CI is green:

1. Merge the release-ready PR into `main`.
2. Create a GitHub Release tagged `v0.5.0` from `main`.
3. The workflow builds a fresh sdist and wheel.
4. The `pypi` job obtains a short-lived OIDC credential.
5. PyPI creates the pending `mailforensics` project on the first successful publish.
6. Verify:

```bash
python -m pip install mailforensics
mailforensics --version
mailforensics demo
```

Do not store a PyPI API token in GitHub secrets for this workflow.
