Open-source software used by py-redact
======================================

py-redact is free software, under the GNU General Public License,
version 3 or later (GPL-3.0-or-later). It is made with, and runs on, other
free and open-source programs and libraries. This is the list of them, with
their licences, grouped by where each one is used. The versions are those
of `uv.lock` for this release; the licences are given as SPDX identifiers
where the projects give one.

The program
-----------

What py-redact needs to run, in every form it is distributed (the wheel,
the AppImage, the RPM and the installers).

| Software | Version | Licence | What it does in py-redact |
|---|---|---|---|
| [Python](https://www.python.org/) | 3.14 or later | PSF-2.0 | The language of the program. |
| [PyMuPDF](https://pymupdf.readthedocs.io/) | 1.28.2 | AGPL-3.0 (or a commercial licence from Artifex) | Reads, draws, redacts and saves the PDF documents. |
| [MuPDF](https://mupdf.com/) | 1.28 (inside PyMuPDF) | AGPL-3.0 (or a commercial licence from Artifex) | The C library under PyMuPDF. |
| [PySide6](https://doc.qt.io/qtforpython-6/) (`pyside6-essentials`) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | The window: Qt for Python. |
| [Shiboken6](https://doc.qt.io/qtforpython-6/shiboken6/) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | The binding layer between PySide6 and Qt. |
| [Qt](https://www.qt.io/) | 6.12 (inside PySide6) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | The toolkit of the window. |

MuPDF and Qt bring third-party libraries of their own (among them
FreeType, HarfBuzz, libjpeg, OpenJPEG, jbig2dec, Little CMS and zlib), each
under its own free licence; the licences are listed in the documentation
of MuPDF and of Qt.

PyMuPDF is under the GNU Affero General Public License. Section 13 of the
GPL version 3 allows a program under it to be combined with a library
under the AGPL version 3, so py-redact may use PyMuPDF; whoever
distributes the combination must respect both licences.

Saving PDF/A and PDF/X
----------------------

Optional: only needed to save in these standards (see "PDF/A and PDF/X" in
the README). py-redact calls the program, which must be installed apart.

| Software | Licence | What it does |
|---|---|---|
| [pdf2iso](https://github.com/nivaca/pdf2iso), by the same author | GPL-3.0-or-later | Converts the redacted copy to PDF/A or PDF/X. |
| [Ghostscript](https://www.ghostscript.com/) | AGPL-3.0-or-later (or a commercial licence from Artifex) | Does the conversion, called by pdf2iso. |
| [pikepdf](https://pikepdf.readthedocs.io/) | MPL-2.0 | Opens encrypted or damaged files for pdf2iso. |
| [qpdf](https://qpdf.sourceforge.io/) | Apache-2.0 | The C++ library under pikepdf. |
| [veraPDF](https://verapdf.org/) (optional) | GPL-3.0-or-later OR MPL-2.0 | Checks the result, when pdf2iso finds it. |

The packages
------------

What is used to build the packages, or goes into them besides the program.

| Software | Licence | Where it is used |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) and uv_build | MIT OR Apache-2.0 | Builds the wheel and the source package; manages the development environment. |
| [python-appimage](https://github.com/niess/python-appimage) | GPL-3.0 | The Python that the AppImage carries. |
| [appimagetool](https://github.com/AppImage/appimagetool) and the AppImage runtime | MIT | Makes the AppImage. |
| [RPM](https://rpm.org/) (`rpmbuild`) | GPL-2.0-or-later | Builds the Fedora package. |
| [Fedora Copr](https://copr.fedorainfracloud.org/) | GPL-2.0-or-later | Builds and serves the Fedora package. |
| [desktop-file-utils](https://www.freedesktop.org/wiki/Software/desktop-file-utils/) | GPL-2.0-or-later | Checks the menu entry when the RPM is built. |
| [hicolor-icon-theme](https://www.freedesktop.org/wiki/Software/icon-theme/) | GPL-2.0-only | Required by the RPM, for the icon folders. |
| [GnuPG](https://gnupg.org/) | GPL-3.0-or-later | Signs the RPM. |

The RPM does not carry PyMuPDF, PySide6 or Qt: it uses Fedora's own
packages of them, under the same licences.

Development and tests
---------------------

Used to write, test and publish py-redact; none of it goes into the
packages.

| Software | Version | Licence | What it does |
|---|---|---|---|
| [pytest](https://pytest.org/) | 9.2.0 | MIT | Runs the tests. |
| [pluggy](https://pluggy.readthedocs.io/) | 1.7.0 | MIT | Plugin system of pytest. |
| [iniconfig](https://github.com/pytest-dev/iniconfig) | 2.3.1 | MIT | Reads pytest's settings. |
| [packaging](https://packaging.pypa.io/) | 26.3 | Apache-2.0 OR BSD-2-Clause | Used by pytest. |
| [Pygments](https://pygments.org/) | 2.21.0 | BSD-2-Clause | Colours pytest's output. |
| [colorama](https://github.com/tartley/colorama) | 0.4.6 | BSD-3-Clause | Colours pytest's output on Windows. |
| [Inkscape](https://inkscape.org/) | 1.4 | GPL-2.0-or-later | Turns the icon's SVG into PNG files (`tools/icons.py`). |
| [Git](https://git-scm.com/) | | GPL-2.0-only | Version control. |
| [GitHub CLI](https://cli.github.com/) (`gh`) | | MIT | Publishes the releases on GitHub. |
| [tea](https://gitea.com/gitea/tea) | | MIT | Publishes the releases on Codeberg. |
| GitHub Actions: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [upload-artifact](https://github.com/actions/upload-artifact) | v7 | MIT | Run the installers and the tests on Windows, macOS and Linux. |

The icons
---------

The toolbar uses the icons of the desktop's own theme, by the names of the
[freedesktop icon naming specification](https://specifications.freedesktop.org/icon-naming-spec/);
py-redact carries no icon theme. Its own icons, for when the desktop has
none, and the program's icon were drawn for it, and are under the
program's licence.
