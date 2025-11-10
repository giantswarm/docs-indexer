from datetime import datetime
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError
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
from random import uniform

try:
    from yaml import CLoader as Loader
except ImportError:
    print("WARNING: Using pure python YAML without accelaration of C libraries")
    from yaml import Loader

from common import html2text
from common import index_settings

OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")
REPOSITORY_BRANCH = os.getenv("REPOSITORY_BRANCH", "main")
REPOSITORY_SUBFOLDER = os.getenv("REPOSITORY_SUBFOLDER")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BASE_URL = os.getenv("BASE_URL")
REPOSITORY_HANDLE = os.getenv("REPOSITORY_HANDLE")
INDEX_NAME = os.getenv("INDEX_NAME")
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

def make_github_api_request(url, token=None, max_retries=3, base_delay=1.0):
    """
    Make a GitHub API request with retry logic and proper error handling.

    Args:
        url: The API endpoint URL
        token: GitHub token for authentication (optional)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay for exponential backoff in seconds

    Returns:
        tuple: (success: bool, response_data: dict or None, status_code: int)
    """
    http = urllib3.PoolManager()
    headers = {}

    if token is not None:
        headers["Authorization"] = f'Bearer {token}'
        logging.info(f'Making authenticated GitHub API request to {url}')
    else:
        logging.info(f'Making unauthenticated GitHub API request to {url}')

    for attempt in range(max_retries + 1):
        try:
            req = http.request("GET", url, headers=headers)

            if req.status == 200:
                data = json.loads(req.data.decode())
                return True, data, req.status
            elif req.status == 403:
                # Check if it's a rate limit issue
                reset_time = req.headers.get('X-RateLimit-Reset')
                remaining = req.headers.get('X-RateLimit-Remaining', '0')

                if remaining == '0' and reset_time:
                    reset_timestamp = int(reset_time)
                    current_time = int(time.time())
                    wait_time = reset_timestamp - current_time + 1

                    if wait_time > 0 and wait_time < 3600:  # Don't wait more than 1 hour
                        logging.warning(f'GitHub API rate limit exceeded. Waiting {wait_time} seconds until reset.')
                        time.sleep(wait_time)
                        continue

                logging.error(f'GitHub API returned 403 Forbidden. This might indicate:')
                logging.error(f'- Invalid or expired GitHub token')
                logging.error(f'- Insufficient permissions for the repository')
                logging.error(f'- Rate limit exceeded (remaining: {remaining})')

                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + uniform(0, 1)
                    logging.info(f'Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries})')
                    time.sleep(delay)
                    continue

                return False, None, req.status
            elif req.status >= 500:
                # Server errors - retry with exponential backoff
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt) + uniform(0, 1)
                    logging.warning(f'GitHub API server error (status {req.status}). Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries})')
                    time.sleep(delay)
                    continue

                logging.error(f'GitHub API server error (status {req.status}) after {max_retries} retries')
                return False, None, req.status
            else:
                # Other client errors (4xx) - don't retry
                logging.error(f'GitHub API client error (status {req.status})')
                return False, None, req.status

        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + uniform(0, 1)
                logging.warning(f'GitHub API request failed with exception: {e}. Retrying in {delay:.2f} seconds... (attempt {attempt + 1}/{max_retries})')
                time.sleep(delay)
                continue
            else:
                logging.error(f'GitHub API request failed after {max_retries} retries: {e}')
                return False, None, 0

    return False, None, 0

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
    Send one HUGO page to opensearch. Arguments:

    es:         opensearchpy.OpenSearch client instance
    root_path:  Root path of the content repository
    path:       File path
    breadcrumb: structured path (list of segments)
    uri:        The URI
    index:      OpenSearch index to write to
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

    # send to OpenSearch
    try:
        es.index(
            index=index,
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
            })


def run():
    """
    Main function executing docs and api-spec indexing
    """
    url = f'https://api.github.com/repos/{REPOSITORY_HANDLE}/commits/{REPOSITORY_BRANCH}'

    # Make GitHub API request with retry logic
    success, data, status_code = make_github_api_request(url, GITHUB_TOKEN)

    if not success:
        logging.error(f'Failed to get last commit SHA from GitHub API after retries. Status: {status_code}')
        logging.error(f'Repository: {REPOSITORY_HANDLE}, Branch: {REPOSITORY_BRANCH}')
        if GITHUB_TOKEN is None:
            logging.error('Consider setting GITHUB_TOKEN environment variable for authenticated requests')
        sys.exit(1)

    logging.info(f'Last {REPOSITORY_HANDLE} commit SHA is {data["sha"]}')

    if OPENSEARCH_ENDPOINT is None:
        logging.error("OPENSEARCH_ENDPOINT isn't configured.")
        sys.exit(1)

    # give opensearch some time
    time.sleep(3)

    es = OpenSearch(hosts=[OPENSEARCH_ENDPOINT])

    index_name = f'{INDEX_NAME}-{data["sha"]}'

    # Check index existence, exit if exists
    check_index(es, index_name)

    # repo name from URL
    (reponame, _) = os.path.basename(REPOSITORY_URL).split(".")
    main_path = SOURCE_PATH + os.sep + reponame

    cloned_sha = clone_repo(REPOSITORY_URL, REPOSITORY_BRANCH, main_path)
    if cloned_sha is False:
        logging.error("ERROR: Could not clone docs repository.")
        logging.error(f"Repository URL: {REPOSITORY_URL}")
        logging.error(f"Branch: {REPOSITORY_BRANCH}")
        logging.error(f"Target path: {main_path}")
        if GITHUB_TOKEN is None:
            logging.error("Note: No GitHub token configured. Private repositories require authentication.")
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

