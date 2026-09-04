import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from opensearchpy import OpenSearch

# Common settings for all opensearch indexes
index_settings = {
    "index": {
        "number_of_shards": 1,
        "analysis": {
            "analyzer": {
                # 'trigram' and 'reverse' analyzers needed for phrase suggester. See mappings/hugo.json.
                "trigram": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "shingle"],
                },
                "reverse": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "reverse"],
                },
            },
            "filter": {
                # 'shingle' filter needed by 'trigram' analyzer.
                "shingle": {
                    "type": "shingle",
                    "min_shingle_size": 2,
                    "max_shingle_size": 3,
                }
            },
        },
    }
}


def html2text(html: str) -> str:
    """
    Return the plain text (UTF-8) representation of the given HTML
    """
    parser = BeautifulSoup(html, features="html.parser")
    return "".join(parser.find_all(string=True))


def index_is_complete(es: OpenSearch, alias: str, index_name: str) -> bool:
    """
    Report whether the index is complete. The alias is moved as the very last
    step of a run, so an index that no alias points at is one an unfinished run
    left behind, however many documents it holds.
    """
    return bool(es.indices.exists_alias(name=alias, index=index_name))


def switch_alias(es: OpenSearch, alias: str, index_name: str) -> None:
    """
    Move alias to index_name in one atomic step, then delete the indices it
    pointed at before. Removing and adding separately would leave the alias
    missing entirely if the run is killed in between.
    """
    previous: list[str] = []
    if es.indices.exists_alias(name=alias):
        previous = [i for i in es.indices.get_alias(name=alias) if i != index_name]

    actions: list[dict[str, Any]] = [
        {"remove": {"index": i, "alias": alias}} for i in previous
    ]
    actions.append({"add": {"index": index_name, "alias": alias}})

    logging.info(f"Moving alias {alias} to index {index_name}")
    es.indices.update_aliases(body={"actions": actions})

    for old_index in previous:
        logging.info(f"Deleting previous index {old_index}")
        try:
            es.indices.delete(index=old_index)
        except Exception:
            logging.error(f"Could not delete index {old_index}")


def prune_incomplete_indices(
    es: OpenSearch, alias: str, suffix_pattern: str, keep: str
) -> None:
    """
    Delete indices of this index set that no alias points at, except keep. Each
    one is a leftover of a run that never reached the alias switch. suffix_pattern
    matches what an indexer appends to alias, so deletion cannot reach an index
    created by anything else.
    """
    own = re.compile(rf"{re.escape(alias)}-{suffix_pattern}")
    indices = es.indices.get_alias(index=f"{alias}-*", ignore_unavailable=True)

    for name, entry in indices.items():
        if name == keep or entry.get("aliases") or not own.fullmatch(name):
            continue

        logging.warning(f"Deleting incomplete index {name} left by an earlier run")
        try:
            es.indices.delete(index=name)
        except Exception:
            logging.error(f"Could not delete index {name}")
