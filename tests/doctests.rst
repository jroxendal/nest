Query Parser Doctests
=====================

These doctests cover the behaviour previously exercised in ``test_parse_query``.

.. doctest::

    >>> from nest.nest import parse_query
    >>> parse_query("keyword") == {'query_string': {'query': 'keyword'}}
    True

    >>> parse_query("date:[2022-01-13 TO now]") == {'range': {'date': {'gte': '2022-01-13', 'lte': 'now'}}}
    True

    >>> parse_query("field:value") == {'match': {'field': 'value'}}
    True

    >>> parse_query("authors>authors.show:false") == {'nested': {'path': 'authors', 'query': {'match': {'authors.show': 'false'}}}}
    True

    >>> parse_query("export>type:pdf") == {'nested': {'path': 'export', 'query': {'match': {'export.type': 'pdf'}}}}
    True

    >>> parse_query("authors>(authors.surname:Strindberg ~ (NOT authors.type:editor))") == {
    ...     'nested': {
    ...         'path': 'authors',
    ...         'query': {
    ...             'bool': {
    ...                 'must': [
    ...                     {'match': {'authors.surname': 'Strindberg'}},
    ...                     {'bool': {'must_not': [{'match': {'authors.type': 'editor'}}]}}
    ...                 ]
    ...             }
    ...         }
    ...     }
    ... }
    True

    >>> parse_query("field:value AND field2:value2") == {
    ...     'bool': {
    ...         'must': [
    ...             {'match': {'field': 'value'}},
    ...             {'match': {'field2': 'value2'}}
    ...         ]
    ...     }
    ... }
    True

    >>> parse_query("field:value AND (field2:value2 OR field3:value3)") == {
    ...     'bool': {
    ...         'must': [
    ...             {'match': {'field': 'value'}},
    ...             {'bool': {'should': [
    ...                 {'match': {'field2': 'value2'}},
    ...                 {'match': {'field3': 'value3'}}
    ...             ],
    ...             'minimum_should_match': 1}}
    ...         ]
    ...     }
    ... }
    True

    >>> def raises_value_error(query):
    ...     try:
    ...         parse_query(query)
    ...     except ValueError:
    ...         return True
    ...     return False

    >>> raises_value_error(">invalid")
    True

    >>> raises_value_error("field>invalid")
    True

    >>> parse_query("sort_date_imprint.date:[1248 TO 2025] AND (export>type:pdf OR mediatype:pdf)") == {
    ...     'bool': {
    ...         'must': [
    ...             {'range': {'sort_date_imprint.date': {'gte': '1248', 'lte': '2025'}}},
    ...             {'bool': {'should': [
    ...                 {'nested': {'path': 'export', 'query': {'match': {'export.type': 'pdf'}}}},
    ...                 {'match': {'mediatype': 'pdf'}}
    ...             ],
    ...             'minimum_should_match': 1}}
    ...         ]
    ...     }
    ... }
    True
