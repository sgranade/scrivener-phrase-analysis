"""
Convert a pyth document to an in-memory string.
"""
from pyth import document

from io import StringIO


class Plaintextifier(object):
    @classmethod
    def convert(cls, doc, newline="\n"):
        writer = Plaintextifier(doc, newline)
        return writer.go()

    def __init__(self, doc, newline):
        self.document = doc
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
            paragraphs.extend(handler(paragraph))

        return paragraphs

    def _convert_paragraph(self, paragraph, prefix=""):
        content = [u"".join(text.content) for text in paragraph.content]
        content = u"".join(content)

        if prefix or self.indent > 0:
            subcontent = []
            indent = "  " * self.indent
            for line in content.splitlines():
                subcontent.append(indent+prefix+line+self.newline)
                if prefix:
                    prefix = "  "
            return subcontent

        else:
            return content.splitlines()

    def _convert_list(self, doc_list, prefix=None):
        self.indent += 1
        subcontent = []
        for entry in doc_list.content:
            for j, paragraph in enumerate(entry.content):
                prefix = "* " if j == 0 else "  "
                handler = self.paragraphDispatch[paragraph.__class__]
                subcontent.extend(handler(paragraph, prefix))
        self.indent -= 1
        return subcontent
