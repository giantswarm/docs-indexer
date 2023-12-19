from bs4 import BeautifulSoup

# Common settings for all elasticsearch indexes
index_settings = {
    "index": {
        "number_of_shards" : 1,
        "analysis": {
            "analyzer": {
                # 'trigram' and 'reverse' analyzers needed for phrase suggester. See mappings/hugo.json.
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
}

def html2text(html):
    """
    Return the plain text (UTF-8) representation of the given HTML
    """
    parser = BeautifulSoup(html, features="html.parser")
    return ''.join(parser.find_all(string=True))
