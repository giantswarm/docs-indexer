# encoding: utf8

from bs4 import BeautifulSoup
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from markdown import markdown
from subprocess import call
from prance import ResolvingParser
import json
import logging
import os
import re
import shutil
import signal
import sys
import time
import toml
import tempfile
import urllib3
import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from pprint import pprint

ELASTICSEARCH_INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX_NAME", "docs")
ELASTICSEARCH_MAPPING = json.load(open("mapping.json", "rb"))
ELASTICSEARCH_ENDPOINT = os.getenv("ELASTICSEARCH_ENDPOINT")
KEEP_PROCESS_ALIVE = os.getenv("KEEP_PROCESS_ALIVE", False)
REPOSITORY_URL = os.getenv("REPOSITORY_URL")
REPOSITORY_BRANCH = os.getenv("REPOSITORY_BRANCH", "master")
REPOSITORY_SUBFOLDER = os.getenv("REPOSITORY_SUBFOLDER")
EXTERNAL_REPOSITORY_SUBFOLDER = os.getenv("EXTERNAL_REPOSITORY_SUBFOLDER")
APIDOCS_BASE_URI = os.getenv("APIDOCS_BASE_URI")
APIDOCS_BASE_PATH = os.getenv("APIDOCS_BASE_PATH")
API_SPEC_FILES = os.getenv("API_SPEC_FILES")

# Path to markdown files
SOURCE_PATH = "/home/indexer/gitcache"


def clone_repo(repo_url, branch, target_path):
    """
    Create a shallow clone of a git repository using a certain branch/tag in
    a given target folder. If the target folder exists, it will be removed
    first and then created again.
    """
    logging.info("Cloning git repository %s, branch '%s'" % (repo_url, branch))

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
    return True


def clone_docs_repos(repo_url, branch, target_path):
    """
    Create a local clone of the docs repository defined by repo_url
    using the given branch plus all the external repositories
    referenced by the docs repo in the src/external-repositories.txt file
    """
    
    cloned = clone_repo(repo_url, branch, main_path)

    # check success
    if not cloned:
        return None

    # check out referenced repositories too
    (reponame, _) = os.path.basename(repo_url).split(".")
    reference_file = os.path.join(SOURCE_PATH, reponame, "src/external-repositories.txt")
    logging.info("reference_file: %s" % reference_file)
    if not os.path.exists(reference_file):
        logging.error("Could not find file %s", reference_file)
    else:
        logging.info("Cloning repositories from %s" % reference_file)
        with open(reference_file, "rb") as ref:
            for line in ref.readlines():
                line = line.strip()
                if line == "":
                    continue

                (repo_url, target_path_prefix) = line.decode().split(" ")
                (reponame, _) = os.path.basename(repo_url).split(".")
                path = os.path.join(SOURCE_PATH, reponame)

                cloned = clone_repo(repo_url, "master", path)
                
                gitpath = os.path.join(path, ".git")

                if not cloned or not os.path.exists(gitpath):
                    print("ERROR: could not clone external repo '%s'" % reponame)
                    continue

                # copy relevant content into main repo
                relevant_stuff_path = path
                if EXTERNAL_REPOSITORY_SUBFOLDER is not None:
                    relevant_stuff_path = os.path.join(relevant_stuff_path, EXTERNAL_REPOSITORY_SUBFOLDER)
                target_path = os.path.join(main_path, target_path_prefix, reponame)
                if not os.path.exists(relevant_stuff_path):
                    print("ERROR: path '%s' does not exist, so cannot be copied and indexed." % relevant_stuff_path)
                    continue

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

            logging.info(record)
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

    # 1. try TOML front matter
    matches = list(re.finditer(r"(\+\+\+)", source_text))
    if len(matches) >= 2:
        front_matter_start = matches[0].start(1)
        front_matter_end = matches[1].start(1)
        try:
            data = toml.loads(source_text[(front_matter_start + 3):front_matter_end])
        except Exception as e:
            logging.error(e)
            logging.warning("Indexing page %s: Error parsing TOML front matter. Please check syntax. Skipping page." % path)
            return (None, None)
    
        text = markdown_to_text(source_text[(front_matter_end+3):])
        for key in data.keys():
            if type(data[key]) == str:
                data[key] = data[key]

        return (data, text)
    
    # 2. Try YAML front matter
    matches = list(re.finditer(r"(\-\-\-)", source_text))
    if len(matches) >= 2:
        front_matter_start = matches[0].start(1)
        front_matter_end = matches[1].start(1)
        try:
            data = yaml.load(source_text[(front_matter_start + 3):front_matter_end], Loader=Loader)
        except Exception as e:
            logging.error(e)
            logging.warning("Indexing page %s: Error parsing front matter. Please check syntax. Skipping page." % path)
            return (None, None)

        text = markdown_to_text(source_text[(front_matter_end+3):])
        for key in data.keys():
            if type(data[key]) == str:
                data[key] = data[key]

        return (data, text)
    
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
    logging.info("Indexing page %s" % uri)
    es.index(
        index=index,
        doc_type="_doc",
        id=uri,
        body=data)


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
    #pprint.pprint(parser.specification["paths"])

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


def index_crds(config_path, repo_path, index, base_path="/reference/cp-k8s-api/"):
    """
    Indexes our API docs based on the Open API specification YAML.

    config_path: Path to crd-docs-generator config file.
    base_path: Path prefix to use for all CRD detail pages
    repo_path: Path where to put the apiextensions reporitory clone
    index: name of the ES index to write the documents to
    """

    config = None
    with open(config_path, "rb") as configfile:
        config = yaml.load(configfile, Loader=Loader)
        
    if "source_repository" not in config:
        raise Exception("Expected 'source_repository' key missing in crd-docs-generator configuration.")
    if "url" not in config["source_repository"]:
        raise Exception("Expected 'source_repository.url' key missing in crd-docs-generator configuration.")
    if "commit_reference" not in config["source_repository"]:
        raise Exception("Expected 'source_repository.commit_reference' key missing in crd-docs-generator configuration.")
    
    skip = []
    if "skip_crds" in config:
        skip = config["skip_crds"]

    repo_url = config["source_repository"]["url"]
    if not repo_url.endswith(".git"):
        repo_url += ".git"

    cloned = clone_repo(repo_url,
                        config["source_repository"]["commit_reference"],
                        repo_path)
    
    if not cloned:
        print("ERROR: could not clone repository % with CRDs" % config["source_repository"]["url"])
        return None
    
    # Treat YAML CRD files in v1 folder

    crd_path = os.path.join(repo_path, "config/crd/v1")
    for name in os.listdir(crd_path):
        if not name.endswith(".yaml"):
            continue

        path = os.path.join(crd_path, name)
        crd = read_crd(path)
        
        if crd["metadata"]["name"] in skip:
            continue

        print("Indexing CRD %s from file %s" % (crd["metadata"]["name"], name))

        title = "%s CRD schema reference" % crd["spec"]["names"]["kind"]
        
        body = crd["metadata"]["name"] + "\n"

        for name in crd["spec"]["names"].keys():
            if type(crd["spec"]["names"][name]) is str:
                body += crd["spec"]["names"][name] + "\n"

        for version in crd["spec"]["versions"]:
            body += version["name"] + "\n"

            if "openAPIV3Schema" in version["schema"]:
                body += "\n".join(collect_properties_text(version["schema"]["openAPIV3Schema"]))

        data = {
            "title": title,
            "uri": base_path + crd["metadata"]["name"] + "/",
            "breadcrumb": [
                "reference",
                "cp-k8s-api",
                crd["metadata"]["name"]
            ],
            "body": body,
            "text": title + "\n" + body,
        }

        es.index(
            index=index,
            doc_type="_doc",
            id=data["uri"],
            body=data)


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
            # if "type" in schema_dict["properties"][prop]:
            #     if schema_dict["properties"][prop]["type"] == "object":
            #         ret.extend(collect_properties_text(schema_dict["properties"][prop]))
            #     if schema_dict["properties"][prop]["type"] == "array":
            #         if "items" in schema_dict["properties"][prop]:
            #             ret.extend(collect_properties_text(schema_dict["properties"][prop]["items"]))
    return ret



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
    time.sleep(3)

    es = Elasticsearch(hosts=[ELASTICSEARCH_ENDPOINT])

    # repo name from URL
    (reponame, _) = os.path.basename(REPOSITORY_URL).split(".")
    main_path = SOURCE_PATH + os.sep + reponame

    path = clone_docs_repos(REPOSITORY_URL, REPOSITORY_BRANCH, main_path)
    if path is None:
        print("ERROR: Could not clone docs main repository.")
        sys.exit(1)

    # get page data
    if REPOSITORY_SUBFOLDER is not None:
        path += os.sep + REPOSITORY_SUBFOLDER
    pages = get_pages(path)

    # create new index
    tempindex = make_indexname(ELASTICSEARCH_INDEX_NAME)
    
    es.indices.create(
        index=tempindex,
        body={
            "settings" : {
                "number_of_shards" : 1,
            },
            "mappings": ELASTICSEARCH_MAPPING
        },
        # include_type_name=false shall be removed once we are on ES 7 or higher
        include_type_name="false")

    # index CRDs
    crd_generator_config_path = os.path.join(main_path, "crd-docs-generator-config.yaml")
    apiextensions_repo_path = os.path.join(SOURCE_PATH, "apiextensions")
    index_crds(crd_generator_config_path, apiextensions_repo_path, tempindex)

    # index API spec
    index_openapi_spec(APIDOCS_BASE_URI, APIDOCS_BASE_PATH, API_SPEC_FILES, tempindex)

    # index docs pages
    for page in pages:
        index_page(page["file_path"], page["path"], page["uri"], tempindex)

    # remove old index if existed, re-create alias
    if es.indices.exists_alias(name=ELASTICSEARCH_INDEX_NAME):
        old_index = es.indices.get_alias(name=ELASTICSEARCH_INDEX_NAME)
        
        # here we assume there is only one index behind this alias
        old_indices = list(old_index.keys())

        if len(old_indices) > 0:
            logging.info("Old index on alias is: %s" % old_indices[0])
            try:
                es.indices.delete_alias(index=old_indices[0], name=ELASTICSEARCH_INDEX_NAME)
            except NotFoundError:
                logging.error("Could not delete index alias for %s" % old_indices[0])
                pass
            try:
                es.indices.delete(index=old_indices[0])
            except:
                logging.error("Could not delete index %s" % old_indices[0])
                pass
    es.indices.put_alias(index=tempindex, name=ELASTICSEARCH_INDEX_NAME)

    if KEEP_PROCESS_ALIVE != False:
        wait_forever()
