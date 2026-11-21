# Registro de cambios

Los cambios notables de py-redact. Las versiones publicadas, con sus
ruedas, AppImages y RPM, están en
[Codeberg](https://codeberg.org/nivaca/py-redact/releases) y
[GitHub](https://github.com/nivaca/py-redact/releases).

## 1.0.9 — 2026-11-19

- En macOS, la aplicación se llama py-redact en la barra de menús (su
  nombre se fija en la información del bundle).
- La AppImage deja fuera las partes de Qt y de Python que el programa no
  usa (de 88 a 73 MB), con una comprobación de que ninguna biblioteca de
  Qt que queda necesita una de las excluidas.
- Copr construye también para Fedora 44.
- La integración continua abre el programa en la pantalla de los tres
  sistemas (`.github/smoke.py`) y guarda las imágenes.

## 1.0.8 — 2026-11-19

Las versiones 1.0.2 a 1.0.7 no se publicaron por separado; sus cambios
están en esta.

- **Guardar ya no detiene la ventana.** La copia se escribe, se revisa y
  se sanea en un proceso propio (`worker.py`, `gui/background.py`), con
  un diálogo que aparece a los 0,4 s y un botón Cancel (Cancelar); la
  copia se escribe como un archivo `.part` y se renombra cuando está
  completa. Con 300 páginas y 5100 recuadros, la detención más larga de
  la ventana bajó de 5,2 s a 0,1 s.
- **Revisiones más rápidas después de guardar**: cada página se lee una
  sola vez para todos sus recuadros (de 140 s a 2 s con 300 páginas y
  5100 recuadros; la revisión de los marcadores, de 85 s a 1 s, y se
  omite cuando la copia no tiene marcadores).
- La búsqueda es diez veces más rápida (de 15 s a 1,5 s con 300
  páginas), y la ventana guarda el texto de cada página hasta que se abre
  otro documento.
- Los instaladores se ejecutan en Windows, macOS y Linux en GitHub
  Actions (`.github/workflows/installers.yml`), con las pruebas sobre el
  programa instalado. Así aparecieron dos fallos, ya corregidos:
  `install.sh` se detenía a medio camino en macOS, y en Windows fallaba
  guardar sobre el original.
- La AppImage instala PyMuPDF y PySide6 en las versiones de `uv.lock`
  (PyMuPDF 1.28.2, PySide6 6.12.0).
- `gui/window.py` se divide en `gui/menus.py`, `gui/saving.py`,
  `gui/thumbnails.py` y `gui/common.py`, y las palabras de una página se
  leen de una sola manera.

## 1.0.1 — 2026-11-19

- Un icono nuevo, en color: una página azul con dos líneas tachadas en
  negro y un marcador rojo, con un dibujo más sencillo para 32 píxeles o
  menos; `tools/icons.py` dibuja todos los PNG a partir de los dos SVG.

## 1.0.0 — 2026-11-19

- **Las páginas se dibujan en procesos propios**, porque MuPDF retiene
  el bloqueo de Python mientras dibuja: un clic en una miniatura responde
  enseguida, y muestra la miniatura ampliada hasta que llega la página.
  Las peticiones de páginas que ya quedaron atrás se descartan, y las
  miniaturas tienen su propio proceso.
- **Instaladores para Linux, macOS y Windows** (`install/`): py-redact
  desde su código fuente, en un entorno propio, con Python 3.14 o
  posterior y una entrada en el menú del sistema. En Windows, pdf2iso se
  ejecuta mediante Python.
- La construcción del RPM reemplaza por el nuevo los RPM anteriores que
  haya en `dist/`.

## 0.4.9 — 2026-11-19

- Una ventana más ágil: cada página se dibuja una vez y se guarda, así
  que un cambio en los recuadros no la vuelve a dibujar; las páginas
  siguiente y anterior se dibujan mientras la ventana está inactiva, y
  solo se redibujan las miniaturas cuyos recuadros cambiaron.

## 0.4.8 — 2026-11-18

- La ventana responde con documentos grandes: miles de recuadros se
  seleccionan en la lista de una vez (de uno en uno tardaba minutos), las
  miniaturas se dibujan de una en una, primero las visibles, y Find and
  redact (Buscar y censurar) lee cada página una sola vez para todos sus
  términos, muestra su avance y puede detenerse.
- La construcción del RPM copia el RPM en `dist/`.

## 0.4.7 — 2026-11-18

- File > Metadata (Archivo > Metadatos): todos los campos de los
  metadatos (información del documento, otros campos, idioma, XMP), cada
  uno con un botón para quitarlo. La copia censurada los recibe al
  guardarse, aunque no tenga recuadros.

## 0.4.6 — 2026-11-17

- Los PDF/A y PDF/X los hace pdf2iso, el nuevo nombre de py-pdfconform;
  el nombre antiguo se sigue buscando.
- El correo de contacto es ahora nicolasvaughan@proton.me.

## 0.4.5 — 2026-11-17

- Los marcadores de la copia censurada se revisan después de guardar: se
  pueden quitar los que nombran lo que había debajo de los recuadros o
  no apuntan a ninguna página, o todos.
- Las etiquetas de página son una clase de información oculta que puede
  quitarse.

## 0.4.4 — 2026-11-17

- La documentación, el registro de cambios del RPM y los comentarios del
  código ya no nombran otros programas de censura. El programa es el
  mismo.

## 0.4.3 — 2026-11-16

- Save siempre escribe un PDF normal. File > Save as (Archivo > Guardar
  como) escribe un PDF normal, PDF/A o PDF/X esta sola vez, en cuanto se
  elige, y no recuerda nada: la clase de PDF ya no es un ajuste.
- Hace falta Python 3.14 o posterior (antes, 3.15); la AppImage trae
  Python 3.14.

## 0.4.2 — 2026-11-16

- File > Save as guarda de inmediato en la clase de PDF elegida (PDF,
  PDF/A, PDF/X); antes solo la elegía, y luego había que usar Save.

## 0.4.1 — 2026-11-16

- Settings > py-pdfconform muestra dónde está el script y cuál se va a
  usar. También se busca en `~/bin` y `~/.local/bin` y con la extensión
  `.py`: al abrir el programa desde el menú del escritorio, a menudo no
  estaba en el PATH, y PDF/A y PDF/X aparecían siempre desactivados.
- El README, en inglés y en español, está completo: qué se necesita,
  cómo instalar, actualizar y desinstalar, qué hay en cada sitio y la
  historia de las versiones.

## 0.4.0 — 2026-11-16

- **Buscar y censurar varias palabras o frases** a la vez, escritas o
  leídas de un archivo, y patrones (correo electrónico, teléfono,
  tarjeta, fecha, identidad, IBAN, en formas estadounidenses o
  españolas), con la opción de dejar visibles algunos caracteres.
- **Códigos de censura**: los conjuntos de la FOIA y de la Privacy Act
  estadounidenses, y los del propio usuario, con un editor que los
  importa y exporta.
- File > Remove hidden information (Archivo > Quitar información
  oculta), clase por clase.
- Bajo el ratón, los recuadros se muestran tal como quedarán; pueden
  fijarse el color del contorno y la opacidad de los recuadros que aún
  no se han aplicado.
- Documentación en inglés y en español (README, `docs/DESCRIPTION.md`,
  `docs/DESCRIPCIÓN_es.md`) con capturas de pantalla hechas por
  `tools/screenshots.py`. Settings tiene el atajo Ctrl+,.

## 0.3.0 — 2026-11-16

- **Una sola herramienta para texto y áreas** (Ctrl+arrastrar para un
  recuadro); doble clic en una palabra o una imagen para censurarla; una
  herramienta de mano.
- Propiedades del recuadro: sin relleno, un texto sobre el recuadro con
  su color, tamaño, alineación y repetición, una nota, bloqueado, y
  guardar como predeterminado. Marcas transparentes con contorno rojo;
  Apply all redactions en el menú del clic derecho.
- La copia se revisa después de guardar; File > Sanitize the document
  (Archivo > Sanear el documento).
- Guardar la copia censurada como PDF/A (1b, 2b, 3b) o PDF/X-4, hecho
  por py-pdfconform cuando está en el PATH.
- Iconos en la barra de herramientas, del tema del escritorio o los del
  propio programa, con descripciones emergentes que indican el atajo.

## 0.2.0 — 2026-11-16

- **Buscar y censurar**: un texto o una expresión regular, en algunas
  páginas o en todas, aunque el texto pase de una línea a otra.
- La herramienta de texto es la activa al arrancar y sigue moviendo
  recuadros; los menús del clic derecho ofrecen lo que corresponde al
  lugar donde se hace clic (una palabra, un recuadro con texto debajo, la
  página); un menú Tools (Herramientas).
- El proyecto de Copr es ahora nivaca/py-redact.

## 0.1.0 — 2026-11-16

- Primera versión: una ventana para censurar documentos PDF. Todo lo que
  queda debajo de cada recuadro se elimina de la copia, y el lugar se
  rellena con el color que se elija; los recuadros pueden repetirse en
  otras páginas.
- Al seleccionar texto se crean recuadros sobre sus líneas; un menú del
  clic derecho para cada recuadro (páginas, color, hacer de su color el
  predeterminado); un diálogo de configuración que se guarda en
  `config.toml` (color de los recuadros nuevos, imágenes, dibujos,
  limpieza).
- La AppImage, el RPM firmado, un ZIP del código fuente y
  `tools/release.py` para publicarlos en GitHub y Codeberg;
  `py-redact --version`.
