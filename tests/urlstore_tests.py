"""
Unit tests for the UrlStore class of the courlan package.
"""

import uuid

from courlan import UrlStore



def test_urlstore():
    'Test all functionality related to the class.'
    example_domain = 'https://www.example.org'
    example_urls = [example_domain + '/' + str(a) for a in range(10000)]
    test_urls = ['https://test.org/' + 'category/' + str(uuid.uuid4())[:20] for a in range(10000)]
    urls = example_urls + test_urls
    # test loading
    url_buffer = UrlStore()._buffer_urls(urls)
    assert sum([len(v) for _, v in url_buffer.items()]) == len(urls)
    my_urls = UrlStore()
    my_urls.add_data(urls)
    assert sum([len(my_urls._load_urls(k)) for k, _ in my_urls.urldict.items()]) == len(urls)
    if my_urls.compressed is False:
        assert sum([len(v) for _, v in my_urls.urldict.items()]) == len(urls)
    # test extension
    extension_urls = ['/1/' + str(a) for a in range(10)]
    my_urls.extend_urls(example_domain, leftseries=extension_urls)
    assert len(my_urls._load_urls(example_domain)) == len(example_urls) + 10
    # test extension + deduplication
    extension_urls = ['/1/' + str(a) for a in range(11)]
    my_urls.extend_urls(example_domain, rightseries=extension_urls)
    url_tuples = my_urls._load_urls(example_domain)
    assert len(url_tuples) == len(example_urls) + 11
    assert url_tuples[-1][0] == '/1/10'
    # get_url
    urlpath1 = my_urls.get_url(example_domain)
    urlpath2 = my_urls.get_url(example_domain)
    assert urlpath1 != urlpath2
    url_tuples = my_urls._load_urls(example_domain)
    # positions
    assert url_tuples[0][0] == urlpath1 and url_tuples[1][0] == urlpath2
    # known or not
    assert my_urls.is_known('https://www.example.org/1')
    candidates = ['https://test.org/category/this', 'https://www.example.org/1', 'https://otherdomain.org/']
    assert my_urls.find_unknown_urls(candidates) == ['https://test.org/category/this', 'https://otherdomain.org/']
    # visited or not
    assert url_tuples[0][1] is True and url_tuples[1][1] is True and url_tuples[2][1] is False
    assert my_urls.has_been_visited(example_domain + urlpath1) is True
    assert my_urls.has_been_visited(example_domain + '/this') is False
    assert my_urls.has_been_visited(example_domain + '/999') is False
    candidates = [example_domain + urlpath1, example_domain + '/this', example_domain + '/999']
    assert my_urls.find_unvisited_urls(candidates) == [example_domain + '/this', example_domain + '/999']

