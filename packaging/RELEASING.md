# Releasing py-redact

1. Set the new version in `pyproject.toml` and `src/py_redact/__init__.py`,
   then in the spec, with a changelog entry:

   ```bash
   rpmdev-bumpspec -n 0.2.0 -c "What changed" \
       -u "Nicolas Vaughan <nivaca@fastmail.com>" packaging/py-redact.spec
   ```

   `tests/test_packaging.py` fails while the versions differ.

2. Commit, then publish:

   ```bash
   uv run python tools/release.py --rpm --no-copr --notes-file NOTES.md
   ```

   This runs the tests; makes the wheel, the source package, the ZIP of the
   source, the AppImage and the signed RPM; tags `vVERSION`; pushes to
   GitHub (`origin`) and Codeberg (`codeberg`); and attaches the files to the
   release on both. `--dry-run` only shows the commands.

## What the RPM build needs

```bash
sudo dnf install rpm-build rpm-sign rpmdevtools python3-devel pyproject-rpm-macros \
    python3-uv-build python3-PyMuPDF python3-pyside6 python3-pytest desktop-file-utils
```

`rpmbuild` checks the build dependencies of the spec, and `%check` runs the
whole test suite on the installed package, so they must be installed here.

## The signing key

The RPMs are signed with the same key as the author's other projects,
`81870643CA221AF90C30554EBE6832CD35994948` (Nicolas Vaughan, RPM signing).
`packaging/build-rpm.sh` pins it, and `--sign` stops if it is not in this
machine's gpg keyring. A copy of the public key is
`packaging/RPM-GPG-KEY-py-redact`.

## Copr

There is no Copr project yet. To make one, and then drop `--no-copr`:

```bash
copr-cli create py-redact --chroot fedora-45-x86_64 --chroot fedora-rawhide-x86_64 \
  --description "Redact PDF documents" \
  --instructions "sudo dnf copr enable nivaca/py-redact && sudo dnf install py-redact"
```
