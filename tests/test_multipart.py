import pytest

from speedy._multipart import parse_content_header, MultiPartFormParser
from speedy.datastructures import UploadFile
from speedy.exceptions import ValidationException


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
    assert parse_content_header(value_content) == expected


def test_parse_body_correct_split():
    body = b'--boundary\r\nContent-Disposition: form-data; name="foo"\r\n\r\nfoo\r\n--boundary\r\nContent-Disposition: form-data; name="boo"\r\n\r\nboo\r\n--boundary--'
    boundary = b'--boundary'
    parser = MultiPartFormParser(body, boundary)
    form_parts = parser.parse_body()
    assert len(form_parts) == 2
    assert form_parts[0].startswith(b'\r\nContent-Disposition: form-data; name="foo"')
    assert form_parts[1].startswith(b'\r\nContent-Disposition: form-data; name="boo"')


def test_parse_body_exceeds_limit():
    body = b'--boundary\r\nContent-Disposition: form-data; name="foo"\r\n\r\nvalue\r\n' * 1001 + b'--boundary--'
    boundary = b'--boundary'
    parser = MultiPartFormParser(body, boundary, multipart_limit=1000)
    with pytest.raises(ValidationException):
        parser.parse_body()


def test_parser_correct_fields():
    body = (
        b'--boundary\r\n'
        b'Content-Disposition: form-data; name="foo"\r\n\r\ntext_foo\r\n'
        b'--boundary\r\n'
        b'Content-Disposition: form-data; name="file"; filename="file.txt"\r\n'
        b'Content-Type: application/octet-stream\r\n\r\ncontent\r\n'
        b'--boundary--'
    )
    boundary = b'--boundary'
    parser = MultiPartFormParser(body, boundary)
    parsed_data = parser.parser()

    field = parsed_data['foo']
    assert field == 'text_foo'

    field = parsed_data['file']
    assert isinstance(field, UploadFile)
    assert field.filename == 'file.txt'
    assert field.content_type == 'application/octet-stream'

    field.file.seek(0)
    assert field.file.read() == b'content'
    assert field.headers.get('content-disposition') == 'form-data'
    assert field.headers.get('content-type') == 'application/octet-stream'


def test_parser_form_parts_empty():
    body = b'--boundary--'
    boundary = b'--boundary'
    parser = MultiPartFormParser(body, boundary)
    parsed_data = parser.parser()
    assert parsed_data == {}


def test_parser_complex_filename():
    body = (
        b'--boundary\r\n'
        b'Content-Disposition: form-data; name="file"; filename*=utf-8\'\'%E2%82%AC%20rates.txt\r\n'
        b'\r\ncontent\r\n'
        b'--boundary--'
    )
    boundary = b'--boundary'
    parser = MultiPartFormParser(body, boundary)
    parsed_data = parser.parser()

    field = parsed_data['file']
    assert isinstance(field, UploadFile)
    assert field.filename == '€ rates.txt'
    assert field.content_type is None

    field.file.seek(0)
    assert field.file.read() == b'content'
    assert field.headers.get('content-disposition') == 'form-data'
