"""
Unit tests for the UrlStore class of the courlan package.
"""

import os
import pickle
import signal
import uuid

from datetime import datetime

import pytest

from courlan import UrlStore


def test_urlstore():
    'Test all functionality related to the class.'

    # sanity checks
    my_urls = UrlStore(validation=False)
    candidates = ['123', 'http://', 'ftp://example.org', 'http://example.org/']
    my_urls.add_urls(candidates)
    assert len(my_urls.urldict) == 1
    firstelem = my_urls.urldict['http://example.org'].tuples[0]
    assert firstelem.urlpath == '/' and firstelem.visited is False
    # sanity checks
    my_urls = UrlStore(validation=True)
    my_urls.add_urls(candidates)
    assert len(my_urls.urldict) == 1
    firstelem = my_urls.urldict['http://example.org'].tuples[0]
    assert firstelem.urlpath == '/' and firstelem.visited is False
    # filters
    my_urls = UrlStore(language='en', strict=True)
    candidates = ['https://de.wikipedia.org/', 'https://www.sitemaps.org/en_GB/protocol.html', 'http://example.com/de/test.html']
    my_urls.add_urls(candidates)
    assert len(my_urls.urldict) == 1 and 'https://www.sitemaps.org' in my_urls.urldict
    my_urls.add_urls(['https://www.sitemaps.org/es/1'], appendleft=['https://www.sitemaps.org/fi/2'])
    assert len(my_urls.urldict['https://www.sitemaps.org'].tuples) == 1

    # try example URLs
    example_domain = 'https://www.example.org'
    example_urls = [example_domain + '/' + str(a) for a in range(10000)]
    test_urls = ['https://test.org/' + str(uuid.uuid4())[:20] for a in range(10000)]
    urls = example_urls + test_urls

    # compression 1
    my_urls = UrlStore(compressed=True)
    url_buffer = UrlStore()._buffer_urls(example_urls)
    my_urls.add_urls(example_urls)
    assert len(pickle.dumps(my_urls)) < len(pickle.dumps(url_buffer))
    assert my_urls.is_known(example_domain + '/100') is True
    # compression 2
    my_urls = UrlStore(compressed=True)
    url_buffer = UrlStore()._buffer_urls(test_urls)
    my_urls.add_urls(test_urls)
    assert len(pickle.dumps(my_urls)) < len(pickle.dumps(url_buffer))

    # test loading
    url_buffer = UrlStore()._buffer_urls(urls)
    assert sum([len(v) for _, v in url_buffer.items()]) == len(urls)
    my_urls = UrlStore()
    my_urls.add_urls(urls)
    assert sum([len(my_urls._load_urls(k)) for k, _ in my_urls.urldict.items()]) == len(urls)
    if my_urls.compressed is False:
        assert sum([len(v.tuples) for _, v in my_urls.urldict.items()]) == len(urls)
    my_urls.add_urls(['https://visited.com/visited'], visited=True)
    assert my_urls.urldict['https://visited.com'].tuples[0].visited is True
    assert my_urls.urldict['https://visited.com'].all_visited is True

    # test extension
    extension_urls = [example_domain + '/1/' + str(a) for a in range(10)]
    my_urls.add_urls(extension_urls)
    assert len(my_urls._load_urls(example_domain)) == len(example_urls) + 10
    # test extension + deduplication
    extension_urls = [example_domain + '/1/' + str(a) for a in range(11)]
    my_urls.add_urls(appendleft=extension_urls)
    url_tuples = my_urls._load_urls(example_domain)
    assert len(url_tuples) == len(example_urls) + 11
    assert url_tuples[-1].urlpath == '/1/10' and url_tuples[0].urlpath == '/1/9'

    # duplicates
    my_urls.add_urls(extension_urls)
    my_urls.add_urls(appendleft=extension_urls)
    assert len(my_urls._load_urls(example_domain)) == len(example_urls) + len(extension_urls)
    assert url_tuples[-1].urlpath == '/1/10' and url_tuples[0].urlpath == '/1/9'

    # get_url
    assert my_urls.urldict[example_domain].timestamp is None
    url1 = my_urls.get_url(example_domain)
    url2 = my_urls.get_url(example_domain)
    assert url1 != url2 and url1 == 'https://www.example.org/1/9'
    url_tuples = my_urls._load_urls(example_domain)
    # positions
    assert url1.endswith(url_tuples[0].urlpath)  and url2.endswith(url_tuples[1].urlpath)
    # timestamp
    assert my_urls.urldict[example_domain].timestamp is not None
    # nothing left
    assert my_urls.urldict[example_domain].all_visited is False
    my_urls.add_urls(['http://tovisit.com/page'])
    assert my_urls.get_url('http://tovisit.com') == 'http://tovisit.com/page'
    assert my_urls.urldict['http://tovisit.com'].all_visited is True
    assert my_urls.get_url('http://tovisit.com') is None

    # known or not
    assert my_urls.is_known('http://tovisit.com/page') is True
    assert my_urls.is_known('https://www.other.org/1') is False
    assert my_urls.is_known('https://www.example.org/1') is True
    candidates = ['https://test.org/category/this', 'https://www.example.org/1', 'https://otherdomain.org/']
    assert my_urls.find_unknown_urls(candidates) == ['https://test.org/category/this', 'https://otherdomain.org/']
    # visited or not
    assert url_tuples[0].visited is True and url_tuples[1].visited is True and url_tuples[2].visited is False
    assert my_urls.has_been_visited('http://tovisit.com/page') is True
    assert my_urls.has_been_visited('https://www.other.org/1') is False
    assert my_urls.has_been_visited(url1) is True
    assert my_urls.has_been_visited(example_domain + '/this') is False
    assert my_urls.has_been_visited(example_domain + '/999') is False
    candidates = [url1, example_domain + '/this', example_domain + '/999']
    assert my_urls.find_unvisited_urls(candidates) == [example_domain + '/this', example_domain + '/999']

    # get download URLs
    downloadable_urls = my_urls.get_download_urls(timelimit=0)
    assert len(downloadable_urls) == 2 and downloadable_urls[0] == 'https://www.example.org/1/7'
    assert (datetime.now() - my_urls.urldict['https://www.example.org'].timestamp).total_seconds() < 0.1
    downloadable_urls = my_urls.get_download_urls()  # limit=10
    assert len(downloadable_urls) == 0
    other_store = UrlStore()
    downloadable_urls = other_store.get_download_urls()
    assert downloadable_urls is None and other_store.done is True

    # schedule
    schedule = other_store.establish_download_schedule()
    assert schedule == []
    schedule = my_urls.establish_download_schedule(max_urls=1, time_limit=1)
    assert len(schedule) == 1 and round(schedule[0][0]) == 1 and schedule[0][1] == 'https://www.example.org/1/6'
    schedule = my_urls.establish_download_schedule(max_urls=6, time_limit=1)
    print(schedule)
    assert len(schedule) == 6 and round(max(s[0] for s in schedule)) == 4


def test_dbdump(capsys):
    'Test cases where the URLs are dumped.'

    # database dump
    other_one = UrlStore()
    other_one.add_urls(['http://print.org/print'])
    other_one.dump_urls()
    captured = capsys.readouterr()
    assert captured.out.strip() == 'http://print.org/print\tFalse'
    interrupted_one = UrlStore()
    interrupted_one.add_urls(['https://www.example.org/1', 'https://www.example.org/10'])
    pid = os.getpid()
    with pytest.raises(SystemExit):
        os.kill(pid, signal.SIGINT)
    captured = capsys.readouterr()
    assert captured.err.strip().endswith('https://www.example.org/10')

