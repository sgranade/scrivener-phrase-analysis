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


def get_scrivener_project_filename(basedir: str):
    """
    Find the base Scrivener file in a Scrivener project.

    :param basedir: The Scrivener project directory.
    :return: The Scrivener project file's name.
    """
    files = glob.glob(os.path.join(os.path.dirname(basedir), '**/*.scrivx'), recursive=True)

    if not files:
        raise FileNotFoundError("No Scrivener file found in the directory {}".format(basedir))
    if len(files) > 1:
        raise RuntimeError("Too many Scrivener files found in the directory {}: {}".format(
            basedir, ", ".join(files)
        ))

    return files[0]


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
