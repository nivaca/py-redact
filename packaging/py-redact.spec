# py-redact, which redacts PDF documents.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
#
# Build with packaging/build-rpm.sh, which makes the source tarball.

Name:           py-redact
Version:        0.4.9
Release:        1%{?dist}
Summary:        Redact PDF documents: remove what lies under boxes drawn on their pages

License:        GPL-3.0-or-later
URL:            https://github.com/nivaca/py-redact
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
# For %%check: the tests run the window (headless).
BuildRequires:  python3-pytest
BuildRequires:  python3-pyside6

# PyMuPDF comes from the package's metadata (pyproject.toml).
# The window: Fedora's PySide6 (pyproject.toml names the PyPI wheel, pyside6-essentials).
Requires:       python3-pyside6
Requires:       hicolor-icon-theme

%description
py-redact redacts PDF documents. Boxes are drawn on the pages, and in the
redacted copy whatever lies under them is removed for good (text, the parts
of images under them, drawings, annotations, form fields); each box is then
filled with a colour of choice, white included. A box can be repeated on
other pages: all, the odd or the even ones, or a list of pages.

The window is in English or Spanish.

%prep
%autosetup -n %{name}-%{version}
# (Fedora's PySide6 is python3-pyside6, which doesn't provide pyside6-essentials)
sed -i '/"pyside6-essentials/d' pyproject.toml

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l py_redact
desktop-file-install --dir=%{buildroot}%{_datadir}/applications packaging/py-redact.desktop
install -d %{buildroot}%{_datadir}/icons
cp -pr src/py_redact/icons/linux/hicolor %{buildroot}%{_datadir}/icons/

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/py-redact.desktop
%pyproject_check_import -e 'py_redact.gui*'
# The whole test suite, on the installed package, with no settings of the
# builder's and the window drawn offscreen.
export HOME="$PWD/check-home" PY_REDACT_CONFIG="$PWD/check-home/config" QT_QPA_PLATFORM=offscreen
%pytest -q tests
%{py3_test_envvars} %{buildroot}%{_bindir}/py-redact --version | grep -q '%{version}'

%files -f %{pyproject_files}
%doc README.md README_es.md docs/DESCRIPTION.md docs/DESCRIPCIÓN_es.md
%{_bindir}/py-redact
%{_datadir}/applications/py-redact.desktop
%{_datadir}/icons/hicolor/*/apps/py-redact.*

%changelog
* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.9-1
- Version 0.4.9: a lighter window (pages rendered once and kept, the next and
  previous rendered ahead, only changed thumbnails redrawn)

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.8-1
- The window answers with large documents: many boxes, thumbnails, Find and
  redact (with progress and Stop); the RPM is also copied to dist/

* Thu Nov 19 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.7-1
- File > Metadata: every field of the metadata, each with a button to remove it;
  the redacted copy gets it when saved

* Tue Nov 17 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.6-1
- PDF/A and PDF/X are made by pdf2iso, the new name of py-pdfconform (the
  old name is still looked for)

* Tue Nov 17 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.5-1
- The bookmarks of the redacted copy are checked after saving, and those that
  give away what was redacted can be removed; page labels are a kind of hidden
  information

* Tue Nov 17 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.4-1
- The documentation, the changelog and the comments no longer name other
  redaction programs

* Tue Nov 17 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.3-1
- Save always writes a plain PDF; File > Save as writes PDF/A or PDF/X this
  once, without remembering it
- Python 3.14 or later is needed (it was 3.15)

* Mon Nov 16 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.2-1
- File > Save as saves at once in the kind of PDF chosen (PDF, PDF/A, PDF/X)

* Mon Nov 16 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.1-1
- Complete documentation in English and Spanish: installing, updating,
  uninstalling, what is where, help, the language of the window, the history of
  the versions, background and sources
- Settings say where py-pdfconform is; it is also looked for in ~/bin and
  ~/.local/bin, and with the .py extension

* Mon Nov 16 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.4.0-1
- Several words or phrases and patterns in Find and redact,
  partial marking, redaction codes, a preview under the mouse, Remove hidden
  information kind by kind; documentation in English and Spanish (README,
  DESCRIPTION)

* Mon Nov 16 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.3.0-1
- Save the redacted copy as PDF/A or PDF/X-4 with py-pdfconform; icons in
  the toolbar; one tool for text and areas, double-click
  a word or an image, box properties (no fill, text over the box, note, locked,
  save as default), apply from the right-click menu, the copy checked after
  saving, sanitize the document, a hand tool

* Mon Nov 16 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.2.0-1
- Find and redact (a text or a regular expression, on some or all pages); the
  text tool is the one on startup; right-click menus that offer what fits where
  they are clicked

* Mon Nov 16 2026 Nicolas Vaughan <nicolasvaughan@proton.me> - 0.1.0-1
- First package: the window, in English or Spanish, with a menu entry that
  also opens PDF files
