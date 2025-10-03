# Search index schema

This indexers create OpenSearch indices with the mappings defined in the files `/mappings/*.json`.

Here is some additional information on the index fields:

- `type`: Document type in a user-friendly spelling, used for filtering.
- `url`: Full URL of the resource.
- `breadcrumb`: List field for breadcrumb items. For a page with `URL = "https://example.com/foo/bar/"` this will be `["foo", "bar"]`.
- `breadcrumb_1` to `breadcrumb_n`: Individual fields for the first, second, third, ... nth breadcrumb item.
- `title`: The title of the document, as intended for representation as a main headline of a search result item. If a document provides several titles, this is supposed to be what users would consider the main headline of the article, or what contains the most valuable content to search for.
- `body`: All text from the main page, excluding the first headline (which is expected to resemble the `title` content).
- `text`: catch-all field. Used for generic search queries where no specific field is selected for a match.
- `date`: Publish date or last modification date for the entry.
- `image_uri`: URL of an image for the entry (optional).
- `uri`: (deprecated)
