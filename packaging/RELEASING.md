# Releasing py-redact

1. Set the new version in `pyproject.toml` and `src/py_redact/__init__.py`,
   then in the spec, with a changelog entry:

   ```bash
   rpmdev-bumpspec -n 0.2.0 -c "What changed" \
       -u "Nicolas Vaughan <nicolasvaughan@proton.me>" packaging/py-redact.spec
   ```

   `tests/test_packaging.py` fails while the versions differ.

2. Commit, then publish:

   ```bash
   uv run python tools/release.py --notes-file NOTES.md
   ```

   This runs the tests; makes the wheel, the source package, the ZIP of the
   source, the AppImage and the signed RPM (always now;
   `--no-rpm` leaves it out); signs every file (`FILE.asc`), with
   `SHA256SUMS` and its signature, and checks each signature with only the
   public key that is published (`tools/sign_release.py`); tags `vVERSION`,
   a signed tag, and checks it (`git tag -v`); pushes to
   GitHub (`origin`) and Codeberg (`codeberg`); and attaches the files to the
   release on both; then it sends the signed source RPM to Copr
   (project nivaca/py-redact). `--dry-run` only shows the commands.

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
`packaging/RPM-GPG-KEY-py-redact`, published with every release.

The same key signs everything a release publishes: the RPM (inside it), each
file (a detached signature, `FILE.asc`), `SHA256SUMS`, and the tag. A
release stops before publishing anything if one signature doesn't verify
with the published key. gpg must have the key's passphrase cached when the
release runs in the background (sign anything once first, e.g. `echo test |
gpg --clearsign -u 81870643CA221AF90C30554EBE6832CD35994948 > /dev/null`).

For GitHub to show the tags as "Verified", the public key must be added to
the GitHub account (Settings > SSH and GPG keys), and its e-mail address be
one of the account's verified addresses.

## Copr

The project is https://copr.fedorainfracloud.org/coprs/nivaca/py-redact/,
built for fedora-44-x86_64, fedora-45-x86_64 and fedora-rawhide-x86_64. Each Copr build needs a
higher version-release than the last, so bump the spec first. `copr-cli`
needs an API token in `~/.config/copr` (it expires after 180 days).
