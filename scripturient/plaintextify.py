"""
Convert a pyth document to an in-memory string.
"""
from pyth import document

from io import StringIO


class Plaintextifier(object):
    @classmethod
    def convert(cls, doc, target=None, newline="\n"):
        if target is None:
            target = StringIO()

        writer = Plaintextifier(doc, target, newline)
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
        paragraphs = []
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

        if prefix or self.indent > 0:
            for line in content.splitlines():
                self.target.write("  " * self.indent)
                self.target.write(prefix)
                self.target.write(line)
                self.target.write(self.newline)
                if prefix:
                    prefix = "  "
        else:
            self.target.write(self.newline.join(content.splitlines()) + self.newline)

    def _convert_list(self, doc_list, prefix=None):
        self.indent += 1
        for entry in doc_list.content:
            for j, paragraph in enumerate(entry.content):
                prefix = "* " if j == 0 else "  "
                handler = self.paragraphDispatch[paragraph.__class__]
                handler(paragraph, prefix)
        self.indent -= 1
