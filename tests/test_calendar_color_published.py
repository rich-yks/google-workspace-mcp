"""The color rules an engine reads are the ones cal_create_event PUBLISHES.

server.py takes calendar_tools' docstrings as the tool descriptions, so the
labels and their priority live in one place, word for word the text x.api
publishes. This pins that wiring: a hand-written docstring in server.py would
silently drift from the twin module.
"""

import asyncio

import calendar_tools
import server


def _descriptions() -> dict[str, str]:
    outils = asyncio.run(server.mcp.list_tools())
    return {t.name: t.description or "" for t in outils}


def test_create_and_update_publish_the_twin_module_docstrings():
    d = _descriptions()
    assert d["cal_create_event"] == calendar_tools.create_event.__doc__
    assert d["cal_update_event"] == calendar_tools.update_event.__doc__


def test_the_published_create_description_carries_the_labels_in_priority_order():
    d = _descriptions()["cal_create_event"]
    positions = [d.index(f"{nom} ({cid})") for cid, nom in calendar_tools._ETIQUETTES.items()]
    assert positions == sorted(positions)
