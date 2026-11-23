Software libre que usa py-redact
================================

py-redact es software libre, bajo la Licencia Pública General de GNU,
versión 3 o posterior (GPL-3.0-or-later). Está hecho con otros programas y
bibliotecas libres y de código abierto, y funciona sobre ellos. Esta es la
lista, con sus licencias, agrupada según dónde se usa cada uno. Las
versiones son las de `uv.lock` para esta versión; las licencias van con su
identificador SPDX cuando el proyecto lo da.

El programa
-----------

Lo que py-redact necesita para funcionar, en todas las formas en que se
distribuye (la rueda, la AppImage, el RPM y los instaladores).

| Software | Versión | Licencia | Qué hace en py-redact |
|---|---|---|---|
| [Python](https://www.python.org/) | 3.14 o posterior | PSF-2.0 | El lenguaje del programa. |
| [PyMuPDF](https://pymupdf.readthedocs.io/) | 1.28.2 | AGPL-3.0 (o una licencia comercial de Artifex) | Lee, dibuja, tacha y guarda los documentos PDF. |
| [MuPDF](https://mupdf.com/) | 1.28 (dentro de PyMuPDF) | AGPL-3.0 (o una licencia comercial de Artifex) | La biblioteca en C sobre la que está PyMuPDF. |
| [PySide6](https://doc.qt.io/qtforpython-6/) (`pyside6-essentials`) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | La ventana: Qt para Python. |
| [Shiboken6](https://doc.qt.io/qtforpython-6/shiboken6/) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | La capa que une PySide6 con Qt. |
| [Qt](https://www.qt.io/) | 6.12 (dentro de PySide6) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | La biblioteca gráfica de la ventana. |

MuPDF y Qt traen bibliotecas de terceros (entre ellas FreeType, HarfBuzz,
libjpeg, OpenJPEG, jbig2dec, Little CMS y zlib), cada una bajo su propia
licencia libre; las licencias están en la documentación de MuPDF y de Qt.

PyMuPDF está bajo la Licencia Pública General Affero de GNU. La sección 13
de la GPL versión 3 permite combinar un programa bajo ella con una
biblioteca bajo la AGPL versión 3, de modo que py-redact puede usar
PyMuPDF; quien distribuya la combinación debe respetar ambas licencias.

Guardar en PDF/A y PDF/X
------------------------

Opcional: solo hace falta para guardar en estos estándares (véase "PDF/A y
PDF/X" en el README). py-redact llama al programa, que se instala aparte.

| Software | Licencia | Qué hace |
|---|---|---|
| [pdf2iso](https://github.com/nivaca/pdf2iso), del mismo autor | GPL-3.0-or-later | Convierte la copia tachada a PDF/A o PDF/X. |
| [Ghostscript](https://www.ghostscript.com/) | AGPL-3.0-or-later (o una licencia comercial de Artifex) | Hace la conversión, llamado por pdf2iso. |
| [pikepdf](https://pikepdf.readthedocs.io/) | MPL-2.0 | Abre para pdf2iso los archivos cifrados o dañados. |
| [qpdf](https://qpdf.sourceforge.io/) | Apache-2.0 | La biblioteca en C++ sobre la que está pikepdf. |
| [veraPDF](https://verapdf.org/) (opcional) | GPL-3.0-or-later OR MPL-2.0 | Revisa el resultado, si pdf2iso lo encuentra. |

Los paquetes
------------

Lo que se usa para construir los paquetes, o va en ellos además del
programa.

| Software | Licencia | Dónde se usa |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) y uv_build | MIT OR Apache-2.0 | Construye la rueda y el paquete fuente; maneja el entorno de desarrollo. |
| [python-appimage](https://github.com/niess/python-appimage) | GPL-3.0 | El Python que lleva la AppImage. |
| [appimagetool](https://github.com/AppImage/appimagetool) y el runtime de AppImage | MIT | Hace la AppImage. |
| [RPM](https://rpm.org/) (`rpmbuild`) | GPL-2.0-or-later | Construye el paquete de Fedora. |
| [Fedora Copr](https://copr.fedorainfracloud.org/) | GPL-2.0-or-later | Construye y sirve el paquete de Fedora. |
| [desktop-file-utils](https://www.freedesktop.org/wiki/Software/desktop-file-utils/) | GPL-2.0-or-later | Revisa la entrada del menú al construir el RPM. |
| [hicolor-icon-theme](https://www.freedesktop.org/wiki/Software/icon-theme/) | GPL-2.0-only | Lo pide el RPM, por las carpetas de los iconos. |
| [GnuPG](https://gnupg.org/) | GPL-3.0-or-later | Firma el RPM. |

El RPM no lleva PyMuPDF, PySide6 ni Qt: usa los paquetes de Fedora, bajo
las mismas licencias.

Desarrollo y pruebas
--------------------

Lo que se usa para escribir, probar y publicar py-redact; nada de esto va
en los paquetes.

| Software | Versión | Licencia | Qué hace |
|---|---|---|---|
| [pytest](https://pytest.org/) | 9.2.0 | MIT | Corre las pruebas. |
| [pluggy](https://pluggy.readthedocs.io/) | 1.7.0 | MIT | El sistema de complementos de pytest. |
| [iniconfig](https://github.com/pytest-dev/iniconfig) | 2.3.1 | MIT | Lee la configuración de pytest. |
| [packaging](https://packaging.pypa.io/) | 26.3 | Apache-2.0 OR BSD-2-Clause | Lo usa pytest. |
| [Pygments](https://pygments.org/) | 2.21.0 | BSD-2-Clause | Colorea la salida de pytest. |
| [colorama](https://github.com/tartley/colorama) | 0.4.6 | BSD-3-Clause | Colorea la salida de pytest en Windows. |
| [Inkscape](https://inkscape.org/) | 1.4 | GPL-2.0-or-later | Convierte el SVG del icono en archivos PNG (`tools/icons.py`). |
| [Git](https://git-scm.com/) | | GPL-2.0-only | Control de versiones. |
| [GitHub CLI](https://cli.github.com/) (`gh`) | | MIT | Publica las versiones en GitHub. |
| [tea](https://gitea.com/gitea/tea) | | MIT | Publica las versiones en Codeberg. |
| GitHub Actions: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [upload-artifact](https://github.com/actions/upload-artifact) | v7 | MIT | Corren los instaladores y las pruebas en Windows, macOS y Linux. |

Los iconos
----------

La barra de herramientas usa los iconos del tema del propio escritorio,
por los nombres de la
[especificación de nombres de iconos de freedesktop](https://specifications.freedesktop.org/icon-naming-spec/);
py-redact no lleva ningún tema de iconos. Los suyos, para cuando el
escritorio no los tiene, y el icono del programa se dibujaron para él, y
están bajo la licencia del programa.
