from collections import OrderedDict
import glob
import os
from typing import Callable, List

from lxml import etree
import nltk
import pyth.document
from pyth.plugins.rtf15.reader import Rtf15Reader
from .plaintextify import Plaintextifier


def _fast_iter(context: etree.iterparse, func: Callable[[str, etree.Element], bool]):
    """
    Iterate over an etree iterparse context and apply a function to each parsed element, freeing memory
    as we go.

    :param context: The iterparse context over which to loop.
    :param func: A function which takes the event string and an etree Element as its arguments and
    returns True if the element should be freed, False if not.
    """
    for event, elem in context:
        if func(event, elem):
            elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    del context


def _select_compiled_binder_item(event: str, elem: etree.Element, project_dir: str, scrivenings: dict) -> bool:
    item_id = elem.get('ID')

    # To deal with nested BinderElements, record the outer-most one's ID
    if event == 'start':
        try:
            scrivenings[item_id]
        except KeyError:
            scrivenings[item_id] = Scrivening(item_id, project_dir=project_dir, include_in_compile=False)
        return False

    if event != 'end':
        raise ValueError('Received unexpected lxml event type '+event)

    scrivening = scrivenings[item_id]

    item_type = elem.get('Type')
    # Only work with text or folder items
    if item_type != 'Text' and item_type != 'Folder':
        return True

    for sub_elem in elem.iterchildren('Title', 'MetaData'):
        if sub_elem.tag == 'Title':
            scrivening.title = sub_elem.text
        elif sub_elem.tag == 'MetaData':
            for inclusion in sub_elem.iterchildren('IncludeInCompile'):
                if inclusion.text == 'Yes':
                    scrivening.include_in_compile = True

    # Deal with the fact that we might be a kid
    parent = elem.getparent()
    if parent.tag == 'Children':
        parent_binder_id = parent.getparent().get('ID')
        scrivenings[parent_binder_id].children.append(scrivening)
        del scrivenings[item_id]

    return True


def _get_scrivener_project_file_path(basedir: str):
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


def _get_scrivening_file_path(basedir: str, scrivening_id: int):
    """
    Find the RTF-formatted file corresponding to a scrivening ID.

    :param basedir: The Scrivener project directory.
    :param scrivening_id: The scrivening ID.
    :return: The scrivening file's path.
    """
    return os.path.join(basedir, 'Files', 'Docs', '{}.rtf'.format(scrivening_id))


def _get_compiled_scrivenings(project_dir, stream):
    """
    Find all pieces of text in the binder that are compiled to the final output.

    :param project_dir: Top-most directory of the Scrivener project.
    :param stream: Open bytes stream containing the Scrivener project file.
    :return: List of top-level scrivenings.
    """
    scrivenings = OrderedDict()
    context = etree.iterparse(stream, events=('start', 'end',), tag='BinderItem')

    def selection_wrapper(event, elem):
        return _select_compiled_binder_item(event, elem, project_dir, scrivenings)

    _fast_iter(context, selection_wrapper)

    return list(scrivenings.values())


class Scrivening(object):
    def __init__(self, binder_id: int, project_dir: str, title: str = None, include_in_compile: bool = True):
        self.id = binder_id
        if title:
            self.title = title
        else:
            self.title = "Scrivening (ID {})".format(binder_id)
        self.include_in_compile = include_in_compile
        self.children = []
        self.file_path = _get_scrivening_file_path(project_dir, binder_id)

        self._rtf = None
        self._text = None

    def rtf(self) -> pyth.document.Document:
        """
        Get the RTF-formatted version of the scrivening.

        :return: The RTF-formatted scrivening in pyth's Document form.
        """
        if not self._rtf:
            try:
                with open(self.file_path, 'rb') as fh:
                    self._rtf = Rtf15Reader.read(fh)
            except FileNotFoundError as e:
                raise FileNotFoundError("Couldn't find the file for scrivening ID {} (title: {})".format(
                    self.id, self.title
                )) from e

        return self._rtf

    def text(self) -> List[str]:
        """
        Get the plain-text version of the scrivening.

        :return: The scrivening in plain text.
        """
        if not self._text:
            self._text = Plaintextifier.convert(self.rtf())

        return self._text


def _get_scrivening_as_flat_text_list(scrivening: Scrivening) -> List[str]:
    contents = []

    try:
        contents.extend(scrivening.text())
    except FileNotFoundError:
        pass

    for child in scrivening.children:
        contents.extend(_get_scrivening_as_flat_text_list(child))

    return contents


def tokenize_scrivening(scrivening: Scrivening) -> List[str]:
    # TODO: this requires the punkt tokenizer model from nltk. Right now it's in Appdata\Roaming\nltk_data
    contents = _get_scrivening_as_flat_text_list(scrivening)
    tokens = nltk.word_tokenize("\n".join(contents))
    return tokens  # TODO should this be a Text() object?


class ScrivenerProject(object):
    def __init__(self, project_dir):
        self.project_dir = project_dir
        try:
            self.project_file = _get_scrivener_project_file_path(project_dir)
        except Exception as e:
            raise ValueError("The project directory does not appear to contain a Scrivener project file") from e
        with open(self.project_file, 'rb') as fh:
            self.scrivenings = _get_compiled_scrivenings(project_dir, fh)
