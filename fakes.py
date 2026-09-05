"""
Test doubles for the opensearchpy client, shared by the test modules.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError


class FakeIndices:
    """
    The subset of the opensearchpy indices client the index/alias handling uses,
    backed by dicts. Records deletions so tests can assert on them.
    """

    def __init__(
        self,
        indices: list[str] | None = None,
        aliases: dict[str, list[str]] | None = None,
        created: dict[str, datetime] | None = None,
    ) -> None:
        self.indices = set(indices or [])
        self.aliases = {k: list(v) for k, v in (aliases or {}).items()}
        self.deleted: list[str] = []
        # Indices default to old enough that no run could still be filling them,
        # which is the ordinary case; pass created to make one look in flight.
        old = datetime.now(timezone.utc) - timedelta(days=1)
        self.created = {i: (created or {}).get(i, old) for i in self.indices}

    def exists(self, index: str) -> bool:
        return index in self.indices

    def create(self, index: str, body: dict[str, Any] | None = None) -> None:
        if index in self.indices:
            raise AssertionError(f"index {index} already exists")
        self.indices.add(index)
        self.created[index] = datetime.now(timezone.utc)

    def get(self, index: str, ignore_unavailable: bool = False) -> dict[str, Any]:
        prefix = index.rstrip("*")
        matched = [i for i in sorted(self.indices) if i.startswith(prefix)]
        if not matched and not index.endswith("*"):
            raise NotFoundError(404, "index_not_found_exception", index)
        return {
            i: {
                "aliases": {
                    a: {} for a, members in self.aliases.items() if i in members
                },
                "settings": {
                    "index": {
                        "creation_date": str(int(self.created[i].timestamp() * 1000))
                    }
                },
            }
            for i in matched
        }

    def exists_alias(self, name: str, index: str | None = None) -> bool:
        # an alias whose last member was removed no longer exists
        if not self.aliases.get(name):
            return False
        if index is None:
            return True
        return index in self.aliases[name]

    def get_alias(
        self,
        name: str | None = None,
        index: str | None = None,
        ignore_unavailable: bool = False,
    ) -> dict[str, Any]:
        if name is not None:
            if not self.aliases.get(name):
                raise NotFoundError(404, "aliases_not_found_exception", name)
            return {i: {"aliases": {name: {}}} for i in self.aliases[name]}

        # index pattern form: every matching index with the aliases it has, if any
        prefix = index.rstrip("*") if index is not None else ""
        return {
            i: {
                "aliases": {
                    a: {} for a, members in self.aliases.items() if i in members
                }
            }
            for i in sorted(self.indices)
            if i.startswith(prefix)
        }

    def delete(self, index: str) -> None:
        self.indices.discard(index)
        self.created.pop(index, None)
        self.deleted.append(index)

    def update_aliases(self, body: dict[str, Any]) -> None:
        for action in body["actions"]:
            if "remove" in action:
                remove = action["remove"]
                self.aliases[remove["alias"]].remove(remove["index"])
            if "add" in action:
                add = action["add"]
                if add["index"] not in self.indices:
                    raise AssertionError(f"aliasing missing index {add['index']}")
                aliased = self.aliases.setdefault(add["alias"], [])
                # adding an alias an index already has is a no-op in OpenSearch
                if add["index"] not in aliased:
                    aliased.append(add["index"])


class FakeOpenSearch:
    def __init__(
        self,
        indices: list[str] | None = None,
        aliases: dict[str, list[str]] | None = None,
        created: dict[str, datetime] | None = None,
    ) -> None:
        self.indices = FakeIndices(indices, aliases, created)
        self.documents: dict[str, dict[str, Any]] = {}

    def index(self, index: str, id: str, body: dict[str, Any]) -> None:
        if index not in self.indices.indices:
            raise AssertionError(f"indexing into missing index {index}")
        self.documents[f"{index}/{id}"] = body


def fake_client(
    indices: list[str] | None = None,
    aliases: dict[str, list[str]] | None = None,
    created: dict[str, datetime] | None = None,
) -> tuple[OpenSearch, FakeIndices]:
    fake = FakeOpenSearch(indices, aliases, created)
    return cast(OpenSearch, fake), fake.indices
