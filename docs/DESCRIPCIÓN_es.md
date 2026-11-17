# py-redact 0.4.3: descripción

## Análisis

py-redact censura documentos PDF. Sobre las páginas se marca lo que debe desaparecer (un nombre, un número de teléfono, un encabezado que se repite, una imagen), y en la copia censurada se elimina del archivo, para siempre, lo que hay debajo de cada recuadro: el texto, la parte de las imágenes que queda debajo, los dibujos que cubre y las anotaciones y campos de formulario que toca. El lugar se rellena con un color, o se deja vacío, y encima puede escribirse un texto (`CENSURADO`, un código de excepción). Lo hice en 2026, en un día, como compañero de otros dos programas míos para PDF, py-foliation (las etiquetas de página) y py-imposition (la imposición para imprenta), de los que tomó su forma.

El requisito central salía de un error frecuente. Tapar un texto con un rectángulo negro lo oculta a la vista, pero el texto sigue en el archivo, y cualquiera puede seleccionarlo, copiarlo o buscarlo. El programa tenía que sacarlo del archivo, y además comprobarlo: no basta con que la copia se vea bien.

Lo demás vino de la manera en que se censura de verdad. Lo que se quiere quitar casi nunca está en un solo lugar: un encabezado aparece en todas las páginas, un nombre en muchas, un número de teléfono quién sabe dónde. Había que poder repetir un recuadro en otras páginas, buscar palabras, listas de palabras y patrones (teléfonos, correos, tarjetas, fechas, números de identidad, cuentas), y dejar visible, si se quiere, una parte de lo encontrado, como los últimos dígitos de una tarjeta. El color del relleno debía poder elegirse, también blanco, o no ponerse ninguno. Y un PDF guarda más de lo que muestran sus páginas: metadatos, adjuntos, marcadores, comentarios, texto oculto, scripts; también eso había que poder quitarlo.

Para lo demás hacía falta lo que se espera de una herramienta de censura completa: una sola herramienta para texto y zonas, propiedades de cada recuadro, códigos de censura, una vista previa al pasar el ratón y la eliminación de la información oculta por clases. La interfaz tenía que estar en español y en inglés, y la copia debía poder guardarse como PDF/A o PDF/X.

## Diseño

El trabajo de fondo lo hace PyMuPDF. py-foliation y py-imposition usan pikepdf, que lee y escribe muy bien la estructura de un PDF, pero censurar es otra cosa: hay que encontrar, dentro del contenido de una página, qué letras, qué píxeles de qué imágenes y qué trazos de qué dibujos caen bajo un rectángulo, y quitarlos sin tocar lo demás. PyMuPDF lo hace con sus anotaciones de censura; pikepdf no tiene nada parecido. Así que py-redact usa PyMuPDF tanto para censurar como para dibujar las páginas, y prescinde de pikepdf.

El programa se divide en módulos pequeños. `redact.py` define el recuadro, un registro inmutable con la página donde se dibujó, su rectángulo, sus páginas, su relleno y su texto, y se ocupa de la censura, de la búsqueda y de la revisión de la copia. `pagesel.py` lee las listas de páginas (`2-10, 15, LAST`), y viene de py-imposition. `patterns.py` tiene los patrones de búsqueda; `codes.py`, los códigos de censura; `hidden.py`, la información oculta; `conform.py`, el paso a PDF/A y PDF/X. `settings.py` y `config.py` guardan la configuración, e `interface.py` traduce la ventana; estos dos últimos vienen de py-foliation.

La ventana está en `gui/`: `window.py` arma los menús, las listas y los diálogos; `canvas.py` dibuja la página y sus recuadros, y recibe el ratón; los diálogos (buscar, propiedades, configuración, códigos, información oculta) tienen cada uno su archivo.

El rectángulo de un recuadro se mide sobre la página tal como se ve, con su giro, desde la esquina superior izquierda; al aplicarlo se pasa a las coordenadas propias de la página, de modo que un recuadro sobre una página girada cubre lo que el ojo ve debajo. Un recuadro repetido conserva su posición en cada página, recortado a su tamaño. Cada cambio de los recuadros va a una pila, para poder deshacerlo.

La copia censurada nunca es el original. Se escribe al lado, como `NOMBRE-redacted.pdf`, por medio de un archivo temporal, y conserva la protección del original. Al escribirla se quitan los objetos que ya nada usa, porque una fuente o una imagen que solo usaba el texto eliminado se quedaría, si no, en el archivo.

## Implementación

Está escrito en Python 3.14 o superior, con PyMuPDF y PySide6 (Qt 6). Son 20 archivos, unas 3900 líneas. El proyecto se maneja con uv.

La página se dibuja con PyMuPDF a la resolución de la pantalla y se muestra en una vista gráfica de Qt, donde los recuadros se dibujan, se mueven y se redimensionan con el ratón. La herramienta *Censurar* decide qué hacer según dónde empieza el arrastre: sobre un texto lo selecciona, en otra parte dibuja un recuadro, y con Ctrl siempre dibuja un recuadro. Un doble clic marca una palabra o una imagen entera. Mientras no se aplican, los recuadros son transparentes, con un contorno rojo; con el ratón encima se ven como quedarán. "Mostrar el resultado" censura en memoria una copia de la página mostrada y la dibuja.

La interfaz está en español y en inglés. Cada texto del programa se busca por su inglés en `locale/es.xml`, y una prueba falla si falta alguno o sobra alguno. La configuración es un archivo TOML pequeño; cada valor se comprueba al leerlo, de modo que un archivo editado a mano no puede detener el programa.

### Búsqueda

La búsqueda lee el texto de cada página como una sucesión de caracteres, cada uno con su rectángulo, con un solo espacio entre palabras y entre líneas. Así una frase se encuentra aunque cruce un salto de línea y esté espaciada de cualquier manera, y cada lugar encontrado se convierte en un recuadro por cada línea que ocupa. Como trabaja con caracteres, puede dejar visibles los primeros o los últimos de cada lugar.

Busca una palabra o frase (con mayúsculas o sin ellas, como palabras completas, o como expresión regular), varias a la vez (escritas o leídas de un archivo de texto) o patrones: direcciones de correo, números de teléfono, de tarjeta de crédito y de identidad, fechas y cuentas bancarias (IBAN). Los patrones son expresiones regulares en dos formas, la de Estados Unidos y la de España y América Latina (`601 312 4478`, `14 de marzo de 2024`, un DNI, una cédula). Un lugar encontrado por dos búsquedas se da una sola vez.

### Revisión de la copia

Después de guardar, py-redact busca cada palabra que estaba debajo de un recuadro en el original, debajo del mismo recuadro, en la copia, sin contar el texto escrito sobre el recuadro. Si alguna todavía puede leerse, un aviso dice dónde.

### PDF/A y PDF/X

El paso a PDF/A o PDF/X-4 lo hace py-pdfconform, otro programa mío, que usa Ghostscript y pikepdf y revisa el resultado. py-redact escribe la copia censurada y se la pasa, si está instalado; si no, esas opciones aparecen desactivadas. Un programa abierto desde el menú del escritorio a menudo no tiene en su PATH la carpeta `~/bin`, donde suele vivir un script como este, así que py-redact también lo busca allí y en `~/.local/bin`, y la configuración permite indicar dónde está. py-pdfconform se ejecuta siempre sin el entorno de Python de py-redact (su entorno virtual o la AppImage), porque, si no, correría con un Python que no tiene pikepdf.

### Proceso y distribución

El trabajo pasó por siete etapas: una ventana que censura, con recuadros repetidos y relleno de cualquier color; los paquetes (la AppImage, el RPM y su publicación); el menú del botón derecho, la configuración y la selección de texto; buscar y censurar; PDF/A y PDF/X; una sola herramienta para texto y zonas, con las propiedades de los recuadros y la revisión de la copia, y por último listas de palabras, patrones, censura parcial, códigos de censura e información oculta. `docs/DESCRIPTION.md` cuenta cada una.

El código se maneja con git, en un repositorio publicado en GitHub (https://github.com/nivaca/py-redact) y en Codeberg (https://codeberg.org/nivaca/py-redact). Un solo script publica cada versión: corre las pruebas, hace la rueda, el paquete fuente, el ZIP, la AppImage y el RPM firmado, pone la etiqueta, publica en los dos sitios y manda el RPM fuente a Copr.

## Validación

Hay 80 pruebas automáticas (`uv run pytest`). Las de la censura hacen documentos con texto, imágenes, anotaciones, campos de formulario, páginas giradas y contraseñas, los censuran y leen el resultado: lo que estaba debajo de un recuadro tiene que haber desaparecido, y lo demás tiene que seguir ahí. Se comprueban también los colores del relleno, la falta de relleno, el texto encima, los recuadros que no caben en una página más pequeña y los tres tratamientos de las imágenes.

La ventana se prueba manejándola como lo haría un usuario, con eventos del ratón sobre la página: dibujar, mover y redimensionar recuadros, seleccionar texto, hacer doble clic, cambiar de herramienta, buscar, marcar, guardar y abrir los menús del botón derecho. Un aviso que en uso normal esperaría un clic hace fallar la prueba en lugar de esperar. El paso a PDF/A y PDF/X se prueba cuando py-pdfconform está instalado.

El RPM vuelve a correr todas las pruebas sobre el paquete instalado, con el Python, el PyMuPDF y el PySide6 de Fedora, y la AppImage censura un documento con su propio Python antes de terminar de armarse. Las ventanas se revisaron además a ojo, con capturas de pantalla en los dos idiomas.

## Plataforma

Funciona en Linux. La AppImage lleva su propio Python, Qt y PyMuPDF, y corre en cualquier Linux con glibc 2.34 o posterior; el RPM es para Fedora 45 y posteriores, y Copr lo construye para cada versión. Desde el código fuente basta Python 3.14 y uv. Para PDF/A y PDF/X hace falta py-pdfconform, con Ghostscript.

Es una aplicación de escritorio y no necesita internet. Nada sale del equipo: los documentos, la configuración y los códigos de censura se quedan en él.

## Ambiente

Lo desarrollé en Fedora Linux 45 con KDE Plasma, con Python 3.14 y uv, y con git, con repositorios en GitHub y Codeberg. Las versiones se publican en los dos sitios y en Copr (https://copr.fedorainfracloud.org/coprs/nivaca/py-redact/).

Para usarlo basta descargar la AppImage, hacerla ejecutable y abrirla; en Fedora, `sudo dnf copr enable nivaca/py-redact` y `sudo dnf install py-redact` lo instalan con su entrada en el menú. La configuración queda en la carpeta de configuración del usuario (`~/.config/py-redact/config.toml` en Linux), con los códigos de censura propios en `codes.xml`.
