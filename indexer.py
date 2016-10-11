# encoding: utf8

from BeautifulSoup import BeautifulSoup
from datetime import datetime
from elasticsearch import Elasticsearch
from markdown import markdown
from subprocess import call
import json
import logging
import os
import re
import shutil
import signal
import sys
import time
import toml


ELASTICSEARCH_INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX_NAME", "docs")
ELASTICSEARCH_DOCTYPE = os.getenv("ELASTICSEARCH_DOCTYPE", "page")
ELASTICSEARCH_MAPPING = json.load(open("mapping.json", "rb"))
ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT")
KEEP_PROCESS_ALIVE = os.getenv("KEEP_PROCESS_ALIVE", False)
REPOSITORY_URL = os.getenv("REPOSITORY_URL")
REPOSITORY_BRANCH = os.getenv("REPOSITORY_BRANCH", "master")
REPOSITORY_SUBFOLDER = os.getenv("REPOSITORY_SUBFOLDER")
EXTERNAL_REPOSITORY_SUBFOLDER = os.getenv("EXTERNAL_REPOSITORY_SUBFOLDER")

# Path to markdown files
SOURCE_PATH = "/gitcache"

def clone_repos(repo_url, branch):
    # local git directory has to be empty, so we
    # make sure it is
    logging.info("Cloning git repository %s, branch '%s'" % (repo_url, branch))
    if os.path.exists(SOURCE_PATH):
        shutil.rmtree(SOURCE_PATH)

    # repo name from URL
    (reponame, ending) = os.path.basename(repo_url).split(".")

    main_path = SOURCE_PATH + os.sep + reponame
    os.makedirs(main_path)
    cmd = ["git", "clone", "-q",
           "--depth", "1",
           "-b", branch,
           repo_url, main_path]
    call(cmd)



    # check out referenced repositories too
    reference_file = os.path.join(SOURCE_PATH, reponame, "external-repositories.txt")
    logging.info("reference_file: %s" % reference_file)
    if os.path.exists(reference_file):
        logging.info("Cloning repositories from %s" % reference_file)
        with open(reference_file, "rb") as ref:
            for line in ref.readlines():
                line = line.strip()
                if line == "":
                    continue
                (repo_url, target_path_prefix) = line.split(" ")
                (reponame, ending) = os.path.basename(repo_url).split(".")
                path = os.path.join(SOURCE_PATH, reponame)
                logging.info("Cloning repository %s to %s" % (reponame, path))
                os.makedirs(path)
                cmd = ["git", "clone", "-q",
                       "--depth", "1",
                       repo_url, path]
                call(cmd)
                # copy relevant content into main repo
                relevant_stuff_path = path
                if EXTERNAL_REPOSITORY_SUBFOLDER is not None:
                    relevant_stuff_path += os.sep + EXTERNAL_REPOSITORY_SUBFOLDER
                target_path = os.path.join(main_path, target_path_prefix, reponame)
                shutil.copytree(relevant_stuff_path, target_path)

                # delete external repository
                shutil.rmtree(path)

    return main_path

def get_pages(root_path):
    """
    Reads the content folder structure and returns a list dicts, one per page.
    Each page dict has these keys.

        path: list of logical uri path elements
        uri: URI of the final rendered page as string
        file_path: physical path of the file, as valid from within this script

    Won't return anything for the home page and other index pages.
    """
    logging.info("Getting pages from %s" % root_path)
    num_root_elements = len(root_path.split(os.sep))
    pages = []
    structured_path = []
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
            if filename != "index.md":
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
    text = ''.join(BeautifulSoup(html).findAll(text=True))
    text = text.replace(" | ", " ")
    text = re.sub(r"[\-]{3,}", "-", text)  # markdown tables
    return text


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
        source_text = file_handler.read()
        try:
            source_text_unicode = source_text.decode("utf8")
        except UnicodeDecodeError, e:
            logging.warn("Not indexing page '%s'. Reason:" % path)
            logging.warn(e)
            logging.debug(source_text)
            return

    # parse front matter
    data = {
        "title": u""
    }
    title = None
    matches = list(re.finditer(r"(\+\+\+)", source_text_unicode))
    if len(matches) < 2:
        logging.warn("Indexing page %s: No front matter found (looking for +++ blah +++)" % path)
        text = markdown_to_text(source_text_unicode)
    else:
        front_matter_start = matches[0].start(1)
        front_matter_end = matches[1].start(1)
        data = toml.loads(source_text[(front_matter_start + 3):front_matter_end])
        text = markdown_to_text(source_text_unicode[(front_matter_end+3):])
        for key in data.keys():
            if type(data[key]) == str:
                data[key] = data[key].decode("utf8")

    data["uri"] = uri
    data["breadcrumb"] = breadcrumb
    data["body"] = text

    # catch-all text field
    data["text"] = data["title"]
    data["text"] += " " + text
    data["text"] += " " + uri
    data["text"] += " " + " ".join(breadcrumb)

    # set main/sub categories "breadcrumb_<i>"
    for i in range(1, len(breadcrumb) + 1):
        data["breadcrumb_%d" % i] = breadcrumb[i - 1]

    # send to ElasticSearch
    logging.info("Indexing page %s" % uri)
    es.index(
        index=index,
        doc_type=ELASTICSEARCH_DOCTYPE,
        id=uri,
        body=data)


def make_indexname(name_prefix):
    """creates a random index name"""
    return name_prefix + "-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")


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
    time.sleep(10)

    es = Elasticsearch(hosts=[ELASTICSEARCH_ENDPOINT])

    path = clone_repos(REPOSITORY_URL, REPOSITORY_BRANCH)

    # get page data
    if REPOSITORY_SUBFOLDER is not None:
        path += os.sep + REPOSITORY_SUBFOLDER
    pages = get_pages(path)

    # generate temporary index name
    tempindex = make_indexname(ELASTICSEARCH_INDEX_NAME)

    es.indices.create(index=tempindex)
    es.indices.put_mapping(index=tempindex,
        doc_type=ELASTICSEARCH_DOCTYPE,
        body=ELASTICSEARCH_MAPPING)

    # index each page into new index
    for page in pages:
        index_page(page["file_path"], page["path"], page["uri"], tempindex)

    # remove old indexif existed, re-create alias
    if es.indices.exists_alias(name=ELASTICSEARCH_INDEX_NAME):
        old_index = es.indices.get_alias(name=ELASTICSEARCH_INDEX_NAME)
        # here we assume there is only one index behind this alias
        old_index = old_index.keys()[0]
        logging.info("Old index on alias is: %s" % old_index)
        try:
            es.indices.delete_alias(index=old_index, name=ELASTICSEARCH_INDEX_NAME)
        except elasticsearch.exceptions.NotFoundError:
            logging.error("Could not delete index alias for %s" % (old_index))
            pass
        try:
            es.indices.delete(index=old_index)
        except:
            logging.error("Could not delete index %s" % old_index)
            pass
    es.indices.put_alias(index=tempindex, name=ELASTICSEARCH_INDEX_NAME)

    if KEEP_PROCESS_ALIVE != False:
        wait_forever()
