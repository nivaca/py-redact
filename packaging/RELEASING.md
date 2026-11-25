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

## Zenodo

Each release leaves in `dist/zenodo/` what goes to Zenodo: the tree of the
tag as `py-redact-VERSION-source.tar.gz`, made with `git archive`, its signature,
a `SHA256SUMS` of only that file with its signature, and the public key.
`tools/release.py` makes it after the tag (`tools/zenodo.py collect`),
and checks every signature there with only the public key.
`tools/zenodo.py collect --packages` also puts the files published with the
release in it, with their signatures.

At the end of each release, `tools/release.py` sends it to Zenodo as a draft
(unless `--no-zenodo`; `tools/zenodo.py upload` does the same on its own),
with the metadata of `.zenodo.json`, the version, the date of the tag,
links to the tag on Codeberg and GitHub, and the whole `README.md` of the tag
as the description, in HTML (headings become bold paragraphs and images are
left out, since Zenodo doesn't take them). What Zenodo's deposit API doesn't
take is then set on the draft through its records API: the languages
(`languages` in `.zenodo.json`), the copyright (the year of the tag and the
first creator), the repository on GitHub, the programming language and the
development status (`programming_language`, `development_status`). If Zenodo already has a published
deposit with the same title, the draft is a new version of it, under the
same concept DOI. The draft is never published by these tools: review it on
Zenodo and publish it there. The token (made at
https://zenodo.org/account/settings/applications/, with deposit:write and
deposit:actions) is kept once in the desktop keyring:

    secret-tool store --label="Zenodo token" service zenodo

`$ZENODO_TOKEN`, if it is set, goes before the keyring.
`tools/zenodo.py check-token` says whether there is one, without showing it.
To try the whole thing first, use `tools/zenodo.py upload --sandbox`, with a
token of sandbox.zenodo.org in the keyring as `service zenodo-sandbox` (or in
`$ZENODO_SANDBOX_TOKEN`); `--dry-run` only shows what would be sent.
