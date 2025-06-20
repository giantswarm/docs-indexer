from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from markdown import markdown
from subprocess import call, check_output, STDOUT
from prance import ResolvingParser
import git
import json
import logging
import os
import re
import shutil
import sys
import time
import tempfile
import urllib3
import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    print("WARNING: Using pure python YAML without accelaration of C libraries")
    from yaml import Loader

from common import html2text
from common import index_settings

ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT", "http://localhost:9200/")
REPOSITORY_BRANCH = os.getenv("REPOSITORY_BRANCH", "main")
REPOSITORY_SUBFOLDER = os.getenv("REPOSITORY_SUBFOLDER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# TODO: validate
BASE_URL = os.getenv("BASE_URL")

# TODO: validate
REPOSITORY_HANDLE = os.getenv("REPOSITORY_HANDLE")

# TODO: validate
INDEX_NAME = os.getenv("INDEX_NAME")

# TODO: validate
TYPE_LABEL = os.getenv("TYPE_LABEL")

WORKDIR = os.getenv("WORKDIR", "/home/indexer")

# Path to markdown files
SOURCE_PATH = f'{WORKDIR}/gitcache'

with open("mappings/hugo.json", "rb") as f:
    DOCS_INDEX_MAPPING = json.load(f)

REPOSITORY_URL = f'https://github.com/{REPOSITORY_HANDLE}.git'
if GITHUB_TOKEN is not None:
    REPOSITORY_URL = f'https://user:{GITHUB_TOKEN}@github.com/{REPOSITORY_HANDLE}.git'


# The date to use if the source does not provide a document
# published/last modified date
DEFAULT_DATE = datetime(1900, 1, 1, 0, 0, 0)

def clone_repo(repo_url, branch, target_path):
    """
    Create a clone with complete history of a git repository using a certain branch/tag in
    a given target folder. If the target folder exists, it will be removed
    first and then created again.
    """
    logging.info(f"Cloning git repository to {target_path}")

    # repo name from URL
    (reponame, _) = os.path.basename(repo_url).split(".")

    if os.path.exists(target_path):
        shutil.rmtree(target_path)

    os.makedirs(target_path, exist_ok=True)

    cmd = ["git", "clone", "-q",
           "-b", branch,
           repo_url, target_path]
    returncode = call(cmd)

    # check success
    if returncode > 0:
        return False
    
    # Get the commit SHA we checked out
    sha = check_output(["git", "-C", f"{target_path}/.git", "rev-parse", "HEAD"],
                       stderr=STDOUT,
                       shell=False)

    return sha.decode().strip()


def get_last_modified(path):
    """
    Traverses a git repository clone under the given path and
    returns a dict of last modified dates, based on the last
    commit to each Markdown file. This requires a git repo clone
    with full history (no shallow clone).
    """
    out = {}

    logging.info(f"Path is {path}")

    repo = git.Repo(path)
    tree = repo.tree()
    
    for blob in tree.traverse():
        if not blob.path.endswith(".md"):
            continue
        gen = list(repo.iter_commits(paths=blob.path, max_count=1))
        commit = gen[0]
        out[blob.path] = datetime.fromtimestamp(commit.committed_date)
    
    return out

def get_pages(root_path):
    """
    Reads the HUGO content folder structure and returns a list of dicts, one per page.
    Each page dict has these keys:

        path: list of logical uri path elements
        uri: URI of the final rendered page as string
        file_path: physical path of the file, as valid from within this script

    Won't return anything for the home page and other index pages.
    """
    logging.info("Getting pages from %s" % root_path)
    num_root_elements = len(root_path.split(os.sep))
    pages = []
    for root, dirs, files in os.walk(root_path):
        if ".git" in dirs:
            dirs.remove(".git")
        if "img" in dirs:
            dirs.remove("img")
        for filename in files:
            if not filename.endswith(".md"):
                continue

            path = root.split(os.sep)[num_root_elements:]
            file_path = root + os.sep + filename
            if filename not in ("index.md", "_index.md"):
                # append name of file (without suffix) as last uri segment
                segment = filename[:-3]
                path.append(segment)

            uri = "/" + "/".join(path) + "/"
            uri = uri.replace("//", "/")

            # HUGO converts mixed case file and folder names to lowercase
            uri = uri.lower()

            record = {
                "path": path,
                "uri": uri,
                "file_path": file_path
            }

            pages.append(record)
    return pages


def markdown_to_text(markdown_text):
    """expects markdown unicode"""
    html = markdown(markdown_text)
    text = html2text(html)
    text = text.replace(" | ", " ")
    text = re.sub(r"[\-]{3,}", "-", text)  # markdown tables
    return text


def get_front_matter(source_text, path):
    """
    Tries to find front matter in the beginning of the document and
    then returns a tuple (frontmatter (dict), text).
    """
    data = {
        "title": u""
    }
    
    # Try YAML front matter
    matches = list(re.finditer(r"(---)\n", source_text))
    if len(matches) >= 2:
        front_matter_start = matches[0].start(1)
        front_matter_end = matches[1].start(1)
        try:
            data = yaml.load(source_text[(front_matter_start + 3):front_matter_end], Loader=Loader)
        except Exception as e:
            logging.error(e)
            logging.warning(f'Indexing page {path}: Error parsing front matter. Please check syntax.')
            return (None, None)

        text = markdown_to_text(source_text[(front_matter_end+3):])

        # use description as fall back for body on otherwise empty pages
        if text.strip() == '' and 'description' in data:
            text = data['description']

        return (data, text.strip())
    
    return (None, None)


def index_page(es, root_path, path, breadcrumb, uri, index, last_modified):
    """
    Send one HUGO page to elasticsearch. Arguments:

    es:         elasticsearch.Elasticsearch client instance
    root_path:  Root path of the content repository
    path:       File path
    breadcrumb: structured path (list of segments)
    uri:        The URI
    index:      Elasticsearch index to write to
    """
    # get document body
    with open(path, "r") as file_handler:
        source_text_unicode = file_handler.read()

    data = None
    text = None

    # parse front matter
    try:
        data, text = get_front_matter(source_text_unicode, path)
    except Exception as e:
        logging.warning("File in %s cannot be parsed for front matter." % path)

    if data is None:
        logging.warning("File in %s did not provide parseable front matter." % path)
        data = {}
    
    data["type"] = TYPE_LABEL
    data["uri"] = uri
    data["url"] = BASE_URL + uri
    data["breadcrumb"] = breadcrumb
    data["body"] = text

    relative_path = path[len(root_path + "/"):]
    data["date"] = last_modified.get(relative_path, DEFAULT_DATE.isoformat() + "+00:00")

    # catch-all text field
    data["text"] = ""
    if "title" in data:
        data["text"] = data["title"]

    if text is not None:
        data["text"] += " " + text

    data["text"] += " " + uri
    data["text"] += " " + " ".join(breadcrumb)

    # set main/sub categories "breadcrumb_<i>"
    for i in range(1, len(breadcrumb) + 1):
        data["breadcrumb_%d" % i] = breadcrumb[i - 1]

    # send to ElasticSearch
    try:
        es.index(
            index=index,
            doc_type="_doc",
            id=uri,
            body=data)
    except Exception as e:
        logging.error(f'Error when indexing page {uri}: {e}')

def read_crd(path):
    with open(path, "rb") as crdfile:
        crd = yaml.load(crdfile, Loader=Loader)
        return crd


def collect_properties_text(schema_dict):
    """
    Recurses into an OpenAPIv3 hierarchy and returns property data valueable for full text indexing.
    That's mainly the property name and a description, if present.
    """
    ret = []
    if "description" in schema_dict:
        ret.append(schema_dict["description"])
    if "properties" in schema_dict:
        for prop in schema_dict["properties"].keys():
            ret.append(prop)
            ret.extend(collect_properties_text(schema_dict["properties"][prop]))
    return ret


def check_index(es, index_name):
    """
    Check if the index already exists
    """
    # Test whether this index already exists
    if es.indices.exists(index_name):
        logging.info(f'Index {index_name} already exists.')
        sys.exit()


def ensure_index(es, index_name):
        es.indices.create(
            index=index_name,
            body={
                "settings" : index_settings,
                "mappings": DOCS_INDEX_MAPPING
            },
            # include_type_name=false shall be removed once we are on ES 7 or higher
            include_type_name="false")


def run():
    """
    Main function executing docs and api-spec indexing
    """
    http = urllib3.PoolManager()
    url = f'https://api.github.com/repos/{REPOSITORY_HANDLE}/commits/{REPOSITORY_BRANCH}'

    req = None
    if GITHUB_TOKEN is None:
        logging.info(f'Getting last {REPOSITORY_HANDLE} commit SHA')
        req = http.request("GET", url)
    else:
        logging.info(f'Getting last {REPOSITORY_HANDLE} commit SHA (authenticated)')
        req = http.request("GET", url, headers={"Authorization": f'Bearer {GITHUB_TOKEN}'})
    
    if req.status >= 400:
        logging.error(f'Error: status {req.status}')
        sys.exit(1)
    data = json.loads(req.data.decode())
    logging.info(f'Last {REPOSITORY_HANDLE} commit SHA is {data["sha"]}')

    if ELASTICSEARCH_ENDPOINT is None:
        logging.error("ELASTICSEARCH_ENDPOINT isn't configured.")
        sys.exit(1)

    # give elasticsearch some time
    time.sleep(3)

    es = Elasticsearch(hosts=[ELASTICSEARCH_ENDPOINT])

    index_name = f'{INDEX_NAME}-{data["sha"]}'

    # Check index existence, exit if exists
    check_index(es, index_name)

    # repo name from URL
    (reponame, _) = os.path.basename(REPOSITORY_URL).split(".")
    main_path = SOURCE_PATH + os.sep + reponame

    cloned_sha = clone_repo(REPOSITORY_URL, REPOSITORY_BRANCH, main_path)
    if cloned_sha is False:
        logging.error("ERROR: Could not clone docs repository.")
        sys.exit(1)
    
    last_modified = get_last_modified(main_path)
    
    # Check again with cloned SHA whether index exist
    # (just in case we got a different SHA than before)
    full_index_name = f'{INDEX_NAME}-{cloned_sha}'
    check_index(es, full_index_name)

    path = main_path

    # get page data
    if REPOSITORY_SUBFOLDER is not None:
        path += os.sep + REPOSITORY_SUBFOLDER
    pages = get_pages(path)

    # create new index
    ensure_index(es, full_index_name)

    # index docs pages
    for page in pages:
        index_page(es, main_path, page["file_path"], page["path"], page["uri"], full_index_name, last_modified)

    # remove old index if existed, re-create alias
    if es.indices.exists_alias(name=INDEX_NAME):
        old_index = es.indices.get_alias(name=INDEX_NAME)
        
        # here we assume there is only one index behind this alias
        old_indices = list(old_index.keys())

        if len(old_indices) > 0:
            logging.info("Old index on alias is: %s" % old_indices[0])
            try:
                es.indices.delete_alias(index=old_indices[0], name=INDEX_NAME)
            except NotFoundError:
                logging.error("Could not delete index alias for %s" % old_indices[0])
                pass
            try:
                es.indices.delete(index=old_indices[0])
            except:
                logging.error("Could not delete index %s" % old_indices[0])
                pass
    es.indices.put_alias(index=full_index_name, name=INDEX_NAME)

