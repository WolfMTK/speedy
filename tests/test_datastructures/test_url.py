from speedy.datastructures import URL


def test_url() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    assert url.scheme == 'https'
    assert url.hostname == 'example.org'
    assert url.port == 8000
    assert url.netloc == 'example.org:8000'
    assert url.username is None
    assert url.password is None
    assert url.path == '/path/to/somewhere'
    assert url.query == 'abc=123'
    assert url.fragment == "anchor"

    new_url = url.replace(scheme='http')
    assert new_url == 'http://example.org:8000/path/to/somewhere?abc=123#anchor'
    assert new_url.scheme == 'http'

    new_url = url.replace(port=None)
    assert new_url == 'https://example.org/path/to/somewhere?abc=123#anchor'
    assert new_url.port is None

    new_url = url.replace(hostname='example.com')
    assert new_url == 'https://example.com:8000/path/to/somewhere?abc=123#anchor'
    assert new_url.hostname == 'example.com'

    ipv6_url = URL('https://[fe::2]:12345')
    new_url = ipv6_url.replace(port=8000)
    assert new_url == 'https://[fe::2]:8000'

    new_url = ipv6_url.replace(username='username', password='password')
    assert new_url == 'https://username:password@[fe::2]:12345'
    assert new_url.netloc == 'username:password@[fe::2]:12345'

    ipv6_url = URL('https://[fe::2]')
    new_url = ipv6_url.replace(port=8000)
    assert new_url == 'https://[fe::2]:8000'

    url = URL('http://u:p@host/')
    assert url.replace(hostname='bar') == URL('http://u:p@bar/')

    url = URL('http://u:p@host:80')
    assert url.replace(port=88) == URL('http://u:p@host:88')

    url = URL('http://host:80')
    assert url.replace(username='u') == URL('http://u@host:80')
