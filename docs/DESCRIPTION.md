How py-redact was made
======================

py-redact is a program for redacting PDF documents: what lies under the
marks drawn on the pages is removed from the file for good, and the place
is filled with a colour, or left empty, with a text over it if wanted.
Nicolas Vaughan made it in November 2026, in a few days, as a companion
to two other PDF programs of his, py-foliation (the page labels of a PDF)
and py-imposition (imposition for printing), from which it took its shape.
Here I explain how it was made, in eleven stages.

It is free software, under the GNU General Public License, version 3 or
later. The redaction is done by PyMuPDF (GNU AGPL 3) and the window by
PySide6 (GNU LGPL 3).

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. A window that removes
------------------------

The first question was which library could do the work. py-foliation and
py-imposition use pikepdf, which reads and writes the structure of a PDF
very well, but redacting is a different thing: it means finding, inside
the content of a page, which letters, which pixels of which images and
which lines of which drawings fall under a rectangle, and taking them out
while the rest stays as it was. pikepdf has nothing for that. PyMuPDF has
it: a redaction annotation marks a rectangle, and applying it removes what
is under it and paints the fill. So py-redact uses PyMuPDF both to redact
and to draw the pages, and pikepdf is not needed.

The first version had what the request asked for, and little more. A mark
is a small immutable record: the page where it was drawn, its rectangle,
its colour, and the pages it is repeated on. The rectangle is measured on
the page as it is shown, with its rotation, from the top left corner; when
it is applied it is turned back into the page's own coordinates, so a mark
on a rotated page covers what the eye sees under it. A mark repeated on
other pages keeps its position, cut to the size of each page. The pages
are written as py-imposition writes them (`2-10, 15, LAST`), and the module
that reads them came from there, with one addition: an open range, `12-`,
goes to the end.

From py-foliation came the rest of the frame: the interface in English and
Spanish, with each text of the program found by its English in an XML file,
and a test that fails if one is missing; the configuration file; the menu
of recent files; changing the language by building the window again; the
password of protected files; drag and drop; and the question before closing
with work not saved. The page is drawn by PyMuPDF at the resolution of the
screen and shown in a Qt graphics view, where the marks are drawn, moved
and resized with the mouse; every change goes on a stack, so that it can be
undone.

A redacted copy is never the original: it is written beside it, as
`NAME-redacted.pdf`, through a temporary file, and protected files keep
their protection. When it is written, the objects that nothing uses any more
are taken out, because a font or a picture that only the removed text used
would otherwise stay in the file.

2. Packages
-----------

The AppImage, the RPM and the release script were adapted from py-foliation.
The AppImage carries a Python of its own with PyMuPDF and PySide6, and
before it is finished it makes a redaction with that Python, to be sure
the bundle works. The RPM uses Fedora's own Python, PyMuPDF and PySide6;
Fedora's PySide6 is not named as PyPI names it, so the spec takes that line
out of `pyproject.toml` before building. The RPM runs the whole test suite
on the installed package, with the window drawn off the screen, and is
signed with the same key as my other programs. One script tags the
version, builds everything, publishes it on GitHub and Codeberg, and sends
the source RPM to Copr, which builds it for each Fedora.

3. Right-click, settings and text
---------------------------------

The first use brought corrections. A mark's pages and colour were
now chosen with the right mouse button. A new mark no longer took the pages
of the one before: a header repeated on every page is not a reason for the
next name to be repeated too. The colour of new marks became a setting of
its own, kept in the configuration file with how pictures and drawings are
treated, and every value is checked when it is read, so that a file edited
by hand can never stop the program.

With them came the marking of text. The words of a page are read with their
rectangles; a drag from one word to another selects all the words between
them in reading order, and a mark is made over each of their lines.

4. Find and redact
------------------

Searching works on the text of a page as a sequence of characters, each
one with its rectangle, with single spaces between words and between lines.
A phrase is therefore found across a line break, however it is spaced, and
each place found becomes one mark for each line it spans. It looks on all
pages, on a list of them, or from the page shown to the end; it lists every
place found with the words around it, and shows any of them on its page.
The menus learnt to offer what fits where they are opened: on a word, to
redact it on that page or on all of them; on a mark with text under it, to
find that text everywhere else.

5. PDF/A and PDF/X
------------------

pdf2iso, another program of mine, converts a PDF to PDF/A or PDF/X-4
with Ghostscript and pikepdf, and checks the result. py-redact writes the
redacted copy and then gives it to pdf2iso, if it is installed; if not,
those choices are greyed out. A program started from the menu of the desktop
often hasn't `~/bin` on its PATH, where a script like this one lives, so
py-redact also looks there and in `~/.local/bin`, and the settings can say
where the script is.

This stage left one lesson. pdf2iso starts with `#!/usr/bin/env
python3`, so it runs with the first Python on the PATH; inside the
environment where py-redact runs (its virtual environment, or the
AppImage), that is py-redact's Python, which hasn't pikepdf. The conversion
failed, and in the build of the RPM the warning that said so waited for a
click that never came. Now pdf2iso is always run without py-redact's
environment, the RPM is built outside it, and in the tests a warning fails
instead of waiting.

6. One tool, and marks with properties
--------------------------------------

There is now one tool for text and areas: over text a drag selects it,
elsewhere it draws a box, and Ctrl+drag always draws a box. A double click
marks one word, or a whole picture. A mark has properties: a fill of any
colour or none at all (the content goes, and nothing is painted), a text
written over it with its colour, size and alignment, repeated along the
mark if wanted, a note shown under the mouse, and a lock; and these can be
saved as the look of new marks. Marks not yet applied are see-through with
a red outline. "Apply all redactions" is at the top of the right-click menu.
A hand tool moves the page.

A redacted document can be checked by hand: by selecting text, by
searching, by moving the marks away. py-redact does it by itself after
saving: every word that was under a mark in the original is
looked for under the same mark in the copy, leaving aside the text written
over the mark, and a warning says where any can still be read.

A document redacted well can still give itself away through its outline: a
heading under a mark often lives on as the title of a bookmark, and a
bookmark may point to pages that were taken out of an excerpt. So the
bookmarks of the copy are checked as well, before anything else is done to
it, such as making it PDF/A. A title is named if it has a word that was
under a mark and nowhere else in the original, or if more than half of its
words were under marks; the second rule matters when a running head still
shows the same words. The user is asked whether to remove those bookmarks,
all of them, or none.

7. Patterns, codes and hidden information
-----------------------------------------

The last group widened the search and what is removed. Find and redact can
now look for several words or phrases at once,
typed or read from a file, and for patterns: e-mail addresses, phone
numbers, card numbers, dates, identity numbers and bank accounts, in their
U.S. forms or in those of Spain and Latin America. Because the search works
on characters, it can leave part of each place visible, such as the last
four digits of a card number. Redaction codes write over a mark the
exemption under which it was redacted; the U.S. FOIA and Privacy Act sets
come with the program, and the user's own sets are kept in an XML file,
which can be exported and imported. With the mouse over a mark, the mark is
shown as it will be once applied. "Remove hidden information" lists what a
document holds besides its pages (metadata, attachments, bookmarks, page
labels,
comments, form fields, hidden text, links and scripts, thumbnails, unused
objects) and how much of each, and removes what is ticked; "Sanitize"
removes all of it.

8. Metadata
-----------

A redacted copy often needs its metadata changed as much as its pages: the
author's name, a title that names the case, a custom field a program left
there. *File ▸ Metadata…* shows all of it: the fields of the document
information (title, author, subject, keywords, creator, producer, the two
dates, trapped), any other fields, the language of the document, and the
XMP packet. Each field has a button to remove it. What is chosen is given
to the copy when it is saved, after any cleaning, and written key by key,
so that a field left out is really gone. A date is shown as `2026-11-17
07:57:28 -05:00` and written back in the PDF form; a date left untouched
keeps the very form it had, so that opening the dialog and closing it
changes nothing.

9. Large documents
------------------

The first real use was a scanned book of 303 pages, and the window, which
had been quick on letters of a few pages, hung. Each cause was found by
timing the window on that book, drawn off the screen at the resolution of
a modern screen. Marking all 6,710 places where a word was found never
finished, because each mark was selected in the list one row at a time,
and each row redrew the list; one selection of all the rows takes a second.
The thumbnails were drawn in groups, and each group stopped the window for
a second; now they are drawn one at a time, those in view first. Find and
redact read every page once for each word it looked for; now it reads each
page once, shows how far it has gone, and can be stopped.

The window was still heavy. Every change of the marks, even selecting one,
drew the whole page again from the PDF, and recomposed all 303 thumbnails.
Now the last pages drawn are kept, only the marks over them are drawn
again, and only the thumbnails whose marks changed. Drawing a mark went
from 190 to 20 milliseconds.

Then a click on a thumbnail still took seconds when the clicks came
quickly. A scanned page takes a fifth of a second to draw, whatever its
size, because its picture has to be decoded, and PyMuPDF keeps Python busy
all that time: a thread doesn't help, since the window can't run while
another thread holds Python. So the pages are drawn in two processes of
their own, one for the page shown and those next to it, and one for the
thumbnails, each with a queue in which the page just asked for goes first
and the pages left behind are dropped. Until the page arrives, its
thumbnail is shown enlarged. The window answers a click in a few
milliseconds; the page is sharp a quarter of a second later, or at once if
it was drawn ahead.

10. Installers
--------------

Version 1.0 added installers for Linux, macOS and Windows, to run py-redact
with Python rather than as a binary. Each makes a virtual environment of
its own, installs py-redact from the source with PyMuPDF and PySide6, which
have wheels for the three systems, and adds it to the system's menu: a
desktop entry with its icons on Linux, a small application in
`~/Applications` on macOS (a script inside the bundle, which runs that
Python), and a Start menu shortcut on Windows, with an icon made from the
program's own pictures. The program needed very little for this: its
configuration already had a folder for each system, and only the way of
running pdf2iso had to change on Windows, where a script is run through
Python. The pages are drawn by processes started the same way on the three
systems, so the program's main modules are guarded against being run again
by those processes.

11. Speed, again
----------------

After version 1.0 I went through the program again looking for what was
still slow, this time on a made-up book of 300 pages with 5,100 marks. The
checks after saving were the worst. For every mark, the words of its page
were read twice, in the original and in the copy, and every word was
compared with the mark through PyMuPDF's rectangles, which cost a few
microseconds each and, in Python, add up: checking the copy took 140
seconds, and checking the bookmarks 85. Now each page is read once for all
its marks, the rectangles are compared as plain numbers, and the bookmarks
are not checked at all when the copy has none. The two checks take two
seconds and one.

The search had the same fault, one level down: it made a rectangle for
every letter of the book, to know where each place found is. With plain
numbers instead, a search of the 300 pages went from 15 seconds to one and
a half, with the same results, on turned pages too. The text of each page
is also kept once read, until another document is opened, so that a second
search, for another word, doesn't read the pages again.

The words of a page were read in two ways, one for selecting text with the
mouse and one for the checks, and the window read them a third time, for a
double click or for the menu of a mark, though the page shown already had
them. Now there is one reading, which tells each word's place, line and
text, and the page shown keeps it.

The window's module had grown to 1,500 lines. Its menus, its saving with
the checks, and its list of pages with the thumbnails went to modules of
their own, as parts mixed into the window's class, so that nothing else
had to change; the window itself is now under 900 lines.

Last, saving. Writing the copy of the book with its 5,100 marks and
checking it took five seconds, in which the window was frozen, for the same
reason as the pages: PyMuPDF keeps Python busy. The writing and each check
now run in a process of their own, started for each, while the window waits
for the result in a loop of its own: it goes on drawing itself, and after
four tenths of a second shows what is being done. Saving keeps its steps in
order, with the question about the bookmarks between them, as before. The
writing can be stopped: the copy is written under another name and renamed
only when it is complete, so that a stopped copy is simply removed. The
checks can't be stopped, since a copy saved but not checked would look as
safe as one checked. The longest stop of the window went from five seconds
to a tenth; the whole saving takes some seconds more, the time of starting
the processes.

The AppImage, too, had drifted from what was tested: it was made by
installing py-redact from PyPI, which gave it the newest PyMuPDF, 2.1,
while the tests and the RPM ran with 1.28. It is now made with the versions
of the project's lock file, the same the tests run with. The installers
still take the newest, which the tests on GitHub's machines now run with on
each change.

Testing
-------

The program has 98 tests (`uv run pytest`). The tests of the redaction make
documents with text, pictures, annotations, form fields, rotated pages and
passwords, redact them, and read the result: what was under a mark must be
gone, and what was not must stay. The window is tested as a user would use
it, with mouse events on the page: drawing, moving and resizing marks,
selecting text, double clicks, the tools, finding, marking, saving, and the
right-click menus. A test checks that every text of the window has its
Spanish translation, and no other. The conversion to PDF/A and PDF/X is
tested when pdf2iso is installed. Another test draws the pages through the
processes of their own, and the installers are checked as far as Linux
allows; the Linux installer was also run in a home folder made for the
test. Since version 1.0.7 the three installers are also run on each change,
on GitHub's machines with Windows, macOS and Linux, which then run the tests
against the program installed and uninstall it. The program had not run on
Windows or macOS before, and this found three faults at once: the `chmod` of
macOS refuses `--`, so the installer stopped halfway there; on Windows, an
open file can't be replaced, and the processes that draw the pages kept the
original open when the copy was to replace it; and an error while renaming
a copy was hidden behind another one. The RPM runs all the tests again with Fedora's own packages. The
program has 30 files, around 5,300 lines.
