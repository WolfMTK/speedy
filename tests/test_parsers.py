from urllib.parse import urlencode

from speedy._parsers import parse_query_string


# TODO: Change the test after adding the dictionary
def test_parse_query_string() -> None:
    query = {
        'value': 10,
        'rating': '10',
        'is_active': True,
        'animal': ['cat', 'wolf']
    }
    query_string = urlencode(query, doseq=True).encode()
    query_string = parse_query_string(query_string)
    for key, value in query.items():
        if isinstance(value, list) and len(value) > 1:
            for i in value:
                assert (key, str(i)) in query_string
        else:
            assert (key, str(value)) in query_string
