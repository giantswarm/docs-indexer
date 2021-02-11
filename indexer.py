from bs4 import BeautifulSoup
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from markdown import markdown
from subprocess import call, check_output, STDOUT
from prance import ResolvingParser
import json
import logging
import os
import re
import shutil
import signal
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


ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT")
KEEP_PROCESS_ALIVE = os.getenv("KEEP_PROCESS_ALIVE", False)
REPOSITORY_URL = os.getenv("REPOSITORY_URL")
REPOSITORY_BRANCH = os.getenv("REPOSITORY_BRANCH", "master")
REPOSITORY_SUBFOLDER = os.getenv("REPOSITORY_SUBFOLDER")
APIDOCS_BASE_URI = os.getenv("APIDOCS_BASE_URI")
APIDOCS_BASE_PATH = os.getenv("APIDOCS_BASE_PATH")
API_SPEC_FILES = os.getenv("API_SPEC_FILES")

# Path to markdown files
SOURCE_PATH = "/home/indexer/gitcache"

DOCS_INDEX_NAME = "docs"
DOCS_INDEX_MAPPING = json.load(open("docs_mapping.json", "rb"))

def clone_repo(repo_url, branch, target_path):
    """
    Create a shallow clone of a git repository using a certain branch/tag in
    a given target folder. If the target folder exists, it will be removed
    first and then created again.
    """
    logging.info("Cloning git repository %s, branch '%s' to %s" % (repo_url, branch, target_path))

    # repo name from URL
    (reponame, _) = os.path.basename(repo_url).split(".")

    if os.path.exists(target_path):
        shutil.rmtree(target_path)

    os.makedirs(target_path, exist_ok=True)

    cmd = ["git", "clone", "-q",
           "--depth", "1",
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

    return sha.strip()


def get_pages(root_path):
    """
    Reads the content folder structure and returns a list of dicts, one per page.
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
            if filename[-3:] != ".md":
                continue

            path = root.split(os.sep)[num_root_elements:]
            file_path = root + os.sep + filename
            if filename not in ("index.md", "_index.md"):
                # append name of file (without suffix) as last uri segment
                segment = filename[:-3]
                path.append(segment)

            uri = "/" + "/".join(path) + "/"
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
    text = ''.join(BeautifulSoup(html, features="html.parser").findAll(text=True))
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


def index_page(path, breadcrumb, uri, index):
    """
    Send one page to elasticsearch. Arguments:

    path: File path
    breadcrumb: structured path (list of segments)
    uri: The URI
    index: Elasticsearch index to write to
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
    
    data["uri"] = uri
    data["breadcrumb"] = breadcrumb
    data["body"] = text

    # catch-all text field
    if "title" in data:
        data["text"] = data["title"]
    else:
        data["text"] = ""

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


def index_openapi_spec(uri, base_path, spec_files, index):
    """
    Indexes our API docs based on the Open API specification YAML
    """
    files = spec_files.split(",")
    tmpdir = tempfile.mkdtemp()

    http = urllib3.PoolManager()

    # download spec files
    for filename in files:
        url = uri + filename
        logging.info("Reading URL %s" % url)
        req = http.request("GET", url)
        path = tmpdir + os.path.sep + os.path.basename(filename)
        with open(path, "w") as outfile:
            outfile.write(req.data.decode())

    # parse spec
    parser = ResolvingParser(tmpdir + os.path.sep + os.path.basename(files[0]))

    for path in parser.specification["paths"]:
        for method in parser.specification["paths"][path]:

            target_uri = base_path + "#operation/" + parser.specification["paths"][path][method]["operationId"]

            logging.info("Indexing %s %s as URL %s" % (method.upper(), path, target_uri))

            title = u"%s - %s %s" % (parser.specification["paths"][path][method]["summary"],
                method.upper(), path)

            # forming body from operation spec
            body = u"The %s API operation\n\n" % parser.specification["paths"][path][method]["operationId"]
            body += markdown_to_text(parser.specification["paths"][path][method]["description"])
            for code in parser.specification["paths"][path][method]["responses"]:
                body += u"\n- %s" % parser.specification["paths"][path][method]["responses"][code]["description"]

            text = title + "\n\n" + body

            # breadcrumb (list of path segments) from base_path
            parts = base_path.split("/")
            breadcrumb = []
            for part in parts:
                if part != "":
                    breadcrumb.append(part)
            breadcrumb.append("#operation/" + parser.specification["paths"][path][method]["operationId"])

            data = {
                "title": title,
                "uri": target_uri,
                "breadcrumb": breadcrumb,
                "body": body,
                "text": text,
            }
            es.index(
                index=index,
                doc_type="_doc",
                id=data["uri"],
                body=data)


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


def wait_forever():
    while True:
        logging.info("Staying alive, doing nothing (KEEP_PROCESS_ALIVE is set).")
        time.sleep(60*60*24)

def sigterm_handler(_signo, _stack_frame):
    logging.info("Terminating due to SIGTERM")
    sys.exit(0)

if __name__ == "__main__":
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    signal.signal(signal.SIGTERM, sigterm_handler)

    # logging setup
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

    if ELASTICSEARCH_ENDPOINT is None:
        logging.error("ELASTICSEARCH_ENDPOINT isn't configured.")
        if KEEP_PROCESS_ALIVE != False:
            wait_forever()
        else:
            sys.exit(1)

    # give elasticsearch some time
    time.sleep(3)

    es = Elasticsearch(hosts=[ELASTICSEARCH_ENDPOINT])

    # repo name from URL
    (reponame, _) = os.path.basename(REPOSITORY_URL).split(".")
    main_path = SOURCE_PATH + os.sep + reponame

    cloned_sha = clone_repo(REPOSITORY_URL, REPOSITORY_BRANCH, main_path)
    if cloned_sha is False:
        print("ERROR: Could not clone docs repository.")
        sys.exit(1)

    path = main_path

    # get page data
    if REPOSITORY_SUBFOLDER is not None:
        path += os.sep + REPOSITORY_SUBFOLDER
    pages = get_pages(path)


    full_index_name = f'{DOCS_INDEX_NAME}-{cloned_sha}'
    if es.indices.exists(name=full_index_name):
        print(f"Index for this docs version {full_index_name} already exists.")
        sys.exit()

    # create new index    
    es.indices.create(
        index=full_index_name,
        body={
            "settings" : {
                "index": {
                    "number_of_shards" : 1,
                    "analysis": {
                        "analyzer": {
                            # 'trigram' and 'reverse' analyzers needed for phrase suggester. See docs_mapping.json.
                            "trigram": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "shingle"]
                            },
                            "reverse": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "reverse"]
                            }
                        },
                        "filter": {
                            # 'shingle' filter needed by 'trigram' analyzer.
                            "shingle": {
                                "type": "shingle",
                                "min_shingle_size": 2,
                                "max_shingle_size": 3
                            }
                        }
                    }
                }
            },
            "mappings": DOCS_INDEX_MAPPING
        },
        # include_type_name=false shall be removed once we are on ES 7 or higher
        include_type_name="false")

    # index API spec
    index_openapi_spec(APIDOCS_BASE_URI, APIDOCS_BASE_PATH, API_SPEC_FILES, full_index_name)

    # index docs pages
    for page in pages:
        index_page(page["file_path"], page["path"], page["uri"], full_index_name)

    # remove old index if existed, re-create alias
    if es.indices.exists_alias(name=DOCS_INDEX_NAME):
        old_index = es.indices.get_alias(name=DOCS_INDEX_NAME)
        
        # here we assume there is only one index behind this alias
        old_indices = list(old_index.keys())

        if len(old_indices) > 0:
            logging.info("Old index on alias is: %s" % old_indices[0])
            try:
                es.indices.delete_alias(index=old_indices[0], name=DOCS_INDEX_NAME)
            except NotFoundError:
                logging.error("Could not delete index alias for %s" % old_indices[0])
                pass
            try:
                es.indices.delete(index=old_indices[0])
            except:
                logging.error("Could not delete index %s" % old_indices[0])
                pass
    es.indices.put_alias(index=full_index_name, name=DOCS_INDEX_NAME)

    if KEEP_PROCESS_ALIVE != False:
        wait_forever()
