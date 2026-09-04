# Indexing of Hubspot blog content
#
# This is the general strategy:
#
# - Initially we index all blog content.
# - The index we create contains a date stamp in the name.
# - Subsequent indexing will only look for changes since the last index update.

from collections.abc import Iterator
from datetime import datetime
from datetime import timezone
import json
import logging
import os
import requests
import sys
from time import sleep
from typing import Any

from opensearchpy import OpenSearch

from common import html2text
from common import index_is_complete
from common import index_settings
from common import prune_incomplete_indices as _prune_incomplete_indices
from common import switch_alias

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")
BASE_URL = os.getenv("BASE_URL")
HUBSPOT_ENDPOINT = "https://api.hubapi.com"
TIME_FORMAT_FINE = "%Y-%m-%dT%H:%M:%S.%fZ"
TIME_FORMAT_COARSE = "%Y-%m-%dT%H:%M:%SZ"
TIME_FORMAT_INDEXNAME = "%Y-%m-%d-%H-%M-%S"
TYPE_LABEL = "Blog"

with open("mappings/blog.json", "rb") as f:
    INDEX_MAPPING = json.load(f)

# Name prefix and alias for our index. Must not contain dashes!
INDEX_NAME_PREFIX = "blog"

# Indices this indexer creates are named after the prefix plus a TIME_FORMAT_INDEXNAME
# timestamp, e.g. blog-2026-08-20-08-51-12.
INDEX_SUFFIX_PATTERN = r"\d{4}(?:-\d{2}){5}"


def get_blog_posts() -> Iterator[dict[str, Any]]:
    """
    Yields all published blog posts from the hubspot API
    """
    if HUBSPOT_ACCESS_TOKEN is None:
        raise RuntimeError("Environment variable HUBSPOT_ACCESS_TOKEN must be set")

    url = f"{HUBSPOT_ENDPOINT}/cms/v3/blogs/posts"
    headers = {
        "accept": "application/json",
        "authorization": "Bearer " + HUBSPOT_ACCESS_TOKEN,
    }
    r = requests.get(url, headers=headers)

    r.raise_for_status()
    body = r.json()

    has_more = True
    while has_more:
        # Iterate result
        for post in body["results"]:
            # Skip unpublished content
            if post["state"] != "PUBLISHED":
                continue

            yield post

        # Paginate
        has_more = False
        if "paging" in body:
            if "next" in body["paging"]:
                if "link" in body["paging"]["next"]:
                    r = requests.get(body["paging"]["next"]["link"], headers=headers)
                    r.raise_for_status()
                    body = r.json()
                    has_more = True


def parse_blog_post(post: dict[str, Any]) -> dict[str, Any]:
    """
    Takes a blog post dict like the hubspot API returns it
    and turn it into a dict that we can index.
    """
    body = html2text(post["postBody"])
    title = html2text(post["htmlTitle"])

    ret = {
        "id": post["id"],
        "type": TYPE_LABEL,
        "breadcrumb": ["blog"],
        "breadcrumb_1": "blog",
        "url": post["url"],
        "uri": post["url"],
        "date": parse_date(post["created"]),
        "title": title,
        "image_uri": post["featuredImage"],
        "body": body,
        "text": f"{title}\n\n{body}",
    }

    return ret


def index_blog_post(es: OpenSearch, index_name: str, data: dict[str, Any]) -> None:
    """
    Write content for one blog post to the index
    """
    id = data["id"]
    try:
        es.index(index=index_name, id=data["id"], body=data)
    except Exception as e:
        logging.error(f"Error when indexing post {id}: {e}")


def parse_date(datestring: str) -> datetime:
    """
    Return a datetime for a date string
    """
    try:
        dt = datetime.strptime(datestring, TIME_FORMAT_FINE)
    except ValueError:
        dt = datetime.strptime(datestring, TIME_FORMAT_COARSE)
    return dt.replace(tzinfo=timezone.utc)


def full_index_name(dt: datetime) -> str:
    """
    Returns an index name based on our prefix and the given date string
    """
    datestring = datetime.strftime(dt, TIME_FORMAT_INDEXNAME)
    return f"{INDEX_NAME_PREFIX}-{datestring}"


def create_index(es: OpenSearch, index_name: str) -> None:
    es.indices.create(
        index=index_name, body={"settings": index_settings, "mappings": INDEX_MAPPING}
    )


def set_index_alias(es: OpenSearch, new_index_name: str) -> None:
    """
    Ensures that index alias INDEX_NAME_PREFIX points to new_index_name only,
    deletes the old index/indices the alias pointed to.
    """
    switch_alias(es, INDEX_NAME_PREFIX, new_index_name)


def prune_incomplete_indices(es: OpenSearch, keep: str) -> None:
    _prune_incomplete_indices(es, INDEX_NAME_PREFIX, INDEX_SUFFIX_PATTERN, keep)


def run() -> None:
    """
    Main function to trigger indexing the blog
    """
    if not HUBSPOT_ACCESS_TOKEN:
        logging.error("Environment variable HUBSPOT_ACCESS_TOKEN must be set")
        sys.exit(1)

    if OPENSEARCH_ENDPOINT is None:
        logging.error("OPENSEARCH_ENDPOINT isn't configured.")
        sys.exit(1)

    # give opensearch some time
    sleep(3)
    logging.info(f"Establish connection to OpenSearch host {OPENSEARCH_ENDPOINT}")
    es = OpenSearch(hosts=[OPENSEARCH_ENDPOINT])

    # Our new target index name
    now_date = datetime.utcnow()
    index_name = full_index_name(now_date)

    # Leftovers of runs that never reached the alias switch. The index about to
    # be created is kept, so this cannot collect the one this run is filling.
    prune_incomplete_indices(es, keep=index_name)

    # An index already under this name is a leftover of an earlier run in the
    # same second, which pruning spares because it is the name we are about to
    # use. Only replace it while no alias points at it.
    if es.indices.exists(index=index_name) and not index_is_complete(
        es, INDEX_NAME_PREFIX, index_name
    ):
        logging.warning(
            f"Deleting incomplete index {index_name} left by an earlier run"
        )
        es.indices.delete(index=index_name)

    logging.info(f"Creating new index {index_name}")

    create_index(es, index_name)

    logging.info("Starting to index hubspot blog")

    count = 0
    for post in get_blog_posts():
        doc = parse_blog_post(post)
        index_blog_post(es, index_name, doc)
        count += 1

    # Set/update index alias
    if count > 0:
        logging.info(f"Updating index alias {INDEX_NAME_PREFIX} to use {index_name}")
        set_index_alias(es, index_name)
    else:
        # Leaving the index would keep an empty one around that no alias points
        # at, and the previous index stays in service.
        logging.info(f"No blog posts found, deleting empty index {index_name}")
        es.indices.delete(index=index_name)

    logging.info("Done")
