from speedy._multipart import parse_content_header

import pytest


@pytest.mark.parametrize(
    'value_content, expected', (
        ('text/html', ('text/html', {})),
        ('text/html; charset=utf-8', ('text/html', {'charset': 'utf-8'})),
        ('text/html; charset=utf-8; boundary=abc123', ('text/html', {'charset': 'utf-8', 'boundary': 'abc123'})),
        ('form-data; name="file"', ('form-data', {'name': 'file'})),
        ('form-data; name="file\\"name"', ('form-data', {'name': 'file"name'})),
        ('', ('', {})),
        (' text/html ; charset=utf-8 ', ('text/html', {'charset': 'utf-8'})),
        ('multipart/form-data; boundary="----WebKitFormBoundary7MA4YWxkTrZu0gW"; charset=utf-8',
         ('multipart/form-data', {'boundary': '----WebKitFormBoundary7MA4YWxkTrZu0gW', 'charset': 'utf-8'})),
    )
)
def test_parse_content_header(value_content: str, expected: tuple[str, dict[str, str]]) -> None:
    print(parse_content_header(value_content), expected)
    assert parse_content_header(value_content) == expected
