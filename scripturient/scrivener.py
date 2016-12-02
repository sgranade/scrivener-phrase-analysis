from collections import OrderedDict
import glob
import os
from typing import Callable, List

from lxml import etree
import pyth.document
from pyth.plugins.rtf15.reader import Rtf15Reader
from .plaintext import PlaintextWriter


def _fast_iter(context: etree.iterparse, func: Callable[[etree.Element], None]):
    """
    Iterate over an etree iterparse context and apply a function to each parsed element, freeing memory
    as we go.

    :param context: The iterparse context over which to loop.
    :param func: A function which takes an etree Element as its sole argument.
    """
    for event, elem in context:
        func(elem)
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    del context


def _select_compiled_binder_item(elem: etree.Element, scrivenings: dict):
    item_id = elem.get('ID')
    item_type = elem.get('Type')
    # Only work with text or folder items
    if item_type != 'Text' and item_type != 'Folder':
        return

    title = "BinderItem ID {}".format(item_id)
    include_in_compile = False

    for sub_elem in elem.iterchildren('Title', 'MetaData', 'Children'):
        if sub_elem.tag == 'Title':
            title = sub_elem.text
        elif sub_elem.tag == 'MetaData':
            for inclusion in sub_elem.iterchildren('IncludeInCompile'):
                if inclusion.text == 'Yes':
                    include_in_compile = True
        else:
            # We've got to recursively process any kids, since this may be a collection
            for binder_item in sub_elem.iterchildren('BinderItem'):
                _select_compiled_binder_item(binder_item, scrivenings)

    if include_in_compile:
        scrivenings[item_id] = title


class ScrivenerProject(object):
    def __init__(self, project_dir):
        self.project_dir = project_dir
        try:
            self.project_file = get_scrivener_project_file_path(project_dir)
        except Exception as e:
            raise ValueError("The project directory does not appear to contain a Scrivener project file") from e
        with open(self.project_file, 'rb') as fh:
            self.scrivenings = get_compiled_scrivenings(fh)

    def read_scrivening(self, scrivening_id: int) -> pyth.document.Document:
        """
        Read an individual scrivening from disk.

        :param scrivening_id: The ID of the scrivening to read. See the scrivenings attribute for more.
        :return: The RTF-formatted scrivening in pyth's Document form.
        """
        try:
            with open(get_scrivening_file_path(self.project_dir, scrivening_id), 'rb') as fh:
                return Rtf15Reader.read(fh)
        except FileNotFoundError as e:
            raise FileNotFoundError("Couldn't find the file for scrivening ID {} (title: {})".format(
                scrivening_id, self.scrivenings[scrivening_id]
            )) from e

    def read_scrivening_as_text(self, scrivening_id: int) -> str:
        stream = PlaintextWriter.write(self.read_scrivening(scrivening_id))
        text = stream.getvalue()
        stream.close()
        return text


def get_scrivener_project_file_path(basedir: str):
    """
    Find the base Scrivener file in a Scrivener project.

    :param basedir: The Scrivener project directory.
    :return: The Scrivener project file's name.
    """
    files = glob.glob(os.path.join(basedir, '*.scrivx'))

    if not files:
        raise FileNotFoundError("No Scrivener project file found in the directory {}".format(basedir))
    if len(files) > 1:
        raise RuntimeError("Too many possible Scrivener project files found in the directory {}: {}".format(
            basedir, ", ".join(files)
        ))

    return files[0]


def get_scrivening_file_path(basedir: str, scrivening_id: int):
    """
    Find the RTF-formatted file corresponding to a scrivening ID.

    :param basedir: The Scrivener project directory.
    :param scrivening_id: The scrivening ID.
    :return: The scrivening file's path.
    """
    return os.path.join(basedir, 'Files', 'Docs', '{}.rtf'.format(scrivening_id))


def get_compiled_scrivenings(stream):
    """
    Find all pieces of text in the binder that are compiled to the final output.

    :param stream: Open bytes stream containing the Scrivener project file.
    :return: Ordered dictionary whose keys are the scrivening IDs and whose values are the title.
    """
    scrivenings = OrderedDict()
    context = etree.iterparse(stream, events=('end',), tag='BinderItem')

    _fast_iter(context, lambda elem:
        _select_compiled_binder_item(elem, scrivenings))

    return scrivenings
