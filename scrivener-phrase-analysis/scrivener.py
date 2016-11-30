from collections import OrderedDict
import glob
import os
from lxml import etree


def _fast_iter(context, func):
    for event, elem in context:
        func(elem)
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    del context


def _process_binder_item(elem: etree.Element, scrivenings: dict):
    item_id = elem.get('ID')
    item_type = elem.get('Type')
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
            for binder_item in sub_elem.iterchildren('BinderItem'):
                _process_binder_item(binder_item, scrivenings)

    if include_in_compile:
        scrivenings[item_id] = title


def get_scrivener_index_filename(basedir):
    """
    Find the base Scrivener file in a Scrivener project.

    :param basedir: The Scrivener project directory.
    :return: The Scrivener index file's name.
    """
    files = glob.glob(os.path.join(os.path.dirname(basedir), '**/*.scrivx'), recursive=True)

    if not files:
        raise FileNotFoundError("No Scrivener file found in the directory {}".format(basedir))
    if len(files) > 1:
        raise RuntimeError("Too many Scrivener files found in the directory {}: {}".format(
            basedir, ", ".join(files)
        ))

    return files


def find_compiled_scrivenings(stream):
    scrivenings = OrderedDict()
    context = etree.iterparse(stream, events=('end',), tag='BinderItem')

    _fast_iter(context, lambda elem:
        _process_binder_item(elem, scrivenings))

    print(scrivenings)
