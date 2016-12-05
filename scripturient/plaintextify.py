"""
Convert a pyth document to an in-memory string.
"""
from __future__ import absolute_import

from pyth import document
from pyth.format import PythWriter

from io import StringIO


class PlaintextWriter(PythWriter):
    @classmethod
    def write(cls, doc, target=None, newline="\n"):
        if target is None:
            target = StringIO()

        writer = PlaintextWriter(doc, target, newline)
        return writer.go()

    def __init__(self, doc, target, newline):
        self.document = doc
        self.target = target
        self.newline = newline
        self.indent = -1
        self.paragraphDispatch = {
            document.List: self._convert_list,
            document.Paragraph: self._convert_paragraph
        }

    def go(self):
        for (i, paragraph) in enumerate(self.document.content):
            handler = self.paragraphDispatch[paragraph.__class__]
            handler(paragraph)
            self.target.write(self.newline)

        self.target.seek(0)
        return self.target

    def _convert_paragraph(self, paragraph, prefix=""):
        content = []
        for text in paragraph.content:
            content.append(u"".join(text.content))
        content = u"".join(content)

        for line in content.splitlines():
            self.target.write("  " * self.indent)
            self.target.write(prefix)
            self.target.write(line)
            self.target.write(self.newline)
            if prefix:
                prefix = "  "

    def _convert_list(self, doc_list, prefix=None):
        self.indent += 1
        for entry in doc_list.content:
            for j, paragraph in enumerate(entry.content):
                prefix = "* " if j == 0 else "  "
                handler = self.paragraphDispatch[paragraph.__class__]
                handler(paragraph, prefix)
        self.indent -= 1
