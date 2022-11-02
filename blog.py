# Indexing of Hubspot blog content
#
# This is the general strategy:
#
# - Initially we index all blog content.
# - The index we create contains a date stamp in the name.
# - Subsequent indexing will only look for changes since the last index update.

from datetime import datetime
from datetime import timezone
import json
import logging
import os
import requests
import sys
from time import sleep

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from common import html2text
from common import index_settings

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")

ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT")
HUBSPOT_ENDPOINT = 'https://api.hubapi.com'
TIME_FORMAT_FINE = '%Y-%m-%dT%H:%M:%S.%fZ'
TIME_FORMAT_COARSE = '%Y-%m-%dT%H:%M:%SZ'
TIME_FORMAT_INDEXNAME = '%Y-%m-%d-%H-%M-%S'
INDEX_MAPPING = json.load(open('mappings/blog.json', 'rb'))

# Name prefix and alias for our index. Must not contain dashes!
INDEX_NAME_PREFIX = 'blog'

def get_blog_posts():
    """
    Yields all published blog posts from the hubspot API
    """
    url = f'{HUBSPOT_ENDPOINT}/cms/v3/blogs/posts'
    headers = {'accept': 'application/json', 'authorization': 'Bearer ' + HUBSPOT_ACCESS_TOKEN}
    r = requests.get(url, headers=headers)

    r.raise_for_status()
    body = r.json()

    has_more = True
    while has_more:
        # Iterate result
        for post in body['results']:
            # Skip unpublished content
            if post['state'] != 'PUBLISHED':
                continue

            yield post

        # Paginate
        has_more = False
        if 'paging' in body:
            if 'next' in body['paging']:
                if 'link' in body['paging']['next']:
                    r = requests.get(body['paging']['next']['link'],
                                     headers=headers,
                                     params=querystring)
                    r.raise_for_status()
                    body = r.json()
                    has_more = True


def parse_blog_post(post):
    """
    Takes a blog post dict like the hubspot API returns it
    and turn it into a dict that we can index.
    """
    body = html2text(post['postBody'])
    title = html2text(post['htmlTitle'])

    ret = {
        'id': post['id'],
        'breadcrumb': ['blog'],
        'breadcrumb_1': 'blog',
        'uri': post['url'],
        'date': parse_date(post['created']),
        'title': title,
        'image_uri': post['featuredImage'],
        'body': body,
        'text': f'{title}\n\n{body}',
    }

    return ret


def index_blog_post(es, index_name, data):
    """
    Write content for one blog post to the index
    """
    id = data['id']
    try:
        es.index(
            index=index_name,
            doc_type="_doc",
            id=data['id'],
            body=data)
    except Exception as e:
        logging.error(f'Error when indexing post {id}: {e}')


def parse_date(datestring):
    """
    Return a datetime for a date string
    """
    try:
        dt = datetime.strptime(datestring, TIME_FORMAT_FINE)
    except ValueError:
        dt = datetime.strptime(datestring, TIME_FORMAT_COARSE)
    return dt.replace(tzinfo=timezone.utc)


def full_index_name(dt):
    """
    Returns an index name based on our prefix and the given date string
    """
    datestring = datetime.strftime(dt, TIME_FORMAT_INDEXNAME)
    return f'{INDEX_NAME_PREFIX}-{datestring}'


def create_index(es, index_name):
    es.indices.create(
        index=index_name,
        body={
            "settings" : index_settings,
            "mappings": INDEX_MAPPING
        },
        # include_type_name=false shall be removed once we are on ES 7 or higher
        include_type_name="false")


def set_index_alias(es, new_index_name):
    """
    Ensures that index alias INDEX_NAME_PREFIX points to new_index_name only,
    deletes the old index/indices the alias pointed to.
    """
    if es.indices.exists_alias(name=INDEX_NAME_PREFIX):
        alias = es.indices.get_alias(name=INDEX_NAME_PREFIX)
        for index_name in list(alias.keys()):
            logging.info(f'Removing alias {INDEX_NAME_PREFIX} => {index_name}')
            try:
                es.indices.delete_alias(index=index_name, name=INDEX_NAME_PREFIX)
            except NotFoundError:
                logging.error(f'Could not delete index alias {INDEX_NAME_PREFIX} => {index_name} (not found)')
                pass

            try:
                logging.info(f'Deleting index {index_name}')
                es.indices.delete(index=index_name)
            except:
                logging.error("Could not delete index %s" % index_name)
                pass
    es.indices.put_alias(index=new_index_name, name=INDEX_NAME_PREFIX)


def run():
    """
    Main function to trigger indexing the blog
    """
    if not HUBSPOT_ACCESS_TOKEN:
        logging.error(f'Environment variable HUBSPOT_ACCESS_TOKEN must be set')
        sys.exit(1)
    
    if ELASTICSEARCH_ENDPOINT is None:
        logging.error("ELASTICSEARCH_ENDPOINT isn't configured.")
        sys.exit(1)
    
    # give elasticsearch some time
    sleep(3)
    logging.info(f'Establish connection to Elasticsearch host {ELASTICSEARCH_ENDPOINT}')
    es = Elasticsearch(hosts=[ELASTICSEARCH_ENDPOINT])

    # Our new target index name
    now_date = datetime.utcnow()
    index_name = full_index_name(now_date)

    logging.info(f'Creating new index {index_name}')

    create_index(es, index_name)

    logging.info(f'Starting to index hubspot blog')

    count = 0
    for post in get_blog_posts():
        doc = parse_blog_post(post)
        index_blog_post(es, index_name, doc)
        count += 1
    
    # Set/update index alias
    if count > 0:
        logging.info(f'Updating index alias {INDEX_NAME_PREFIX} to use {index_name}')
        set_index_alias(es, index_name)
    else:
        logging.info(f'No new/updated blog posts found.')

    logging.info(f'Done')
