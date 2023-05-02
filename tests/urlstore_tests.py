"""
Unit tests for the UrlStore class of the courlan package.
"""

import gc
import os
import pickle
import signal
import sys
import uuid

from datetime import datetime

import pytest

from courlan import UrlStore


def test_urlstore():
    "Test all functionality related to the class."

    # sanity checks
    my_urls = UrlStore()
    candidates = [
        "123",
        "http://",
        "ftp://example.org",
        "https://example.org/",
        "http://example.org/",
        "https://example.org/1",
        "http://example.org/1",
    ]
    my_urls.add_urls(candidates)
    assert len(my_urls.urldict) == 1 and "http://example.org" not in my_urls.urldict
    assert len(my_urls.urldict["https://example.org"].tuples) == 2
    firstelem = my_urls.urldict["https://example.org"].tuples[0]
    assert firstelem.urlpath == "/" and firstelem.visited is False
    # reset
    num, _, _ = gc.get_count()
    my_urls.reset()
    num2, _, _ = gc.get_count()
    assert len(my_urls.urldict) == 0
    assert num2 < num

    candidates = [
        "http://example.org/",
        "https://example.org/",
        "http://example.org/1",
        "https://example.org/1",
    ]
    my_urls.add_urls(candidates)
    assert len(my_urls.urldict) == 1 and "http://example.org" not in my_urls.urldict
    assert len(my_urls.urldict["https://example.org"].tuples) == 2

    # rules
    rules = pickle.loads(
        b"\x80\x03curllib.robotparser\nRobotFileParser\nq\x00)\x81q\x01}q\x02(X\x07\x00\x00\x00entriesq\x03]q\x04X\r\x00\x00\x00default_entryq\x05NX\x0c\x00\x00\x00disallow_allq\x06\x89X\t\x00\x00\x00allow_allq\x07\x89X\x03\x00\x00\x00urlq\x08X\x1f\x00\x00\x00https://sitemaps.org/robots.txtq\tX\x04\x00\x00\x00hostq\nX\x0c\x00\x00\x00sitemaps.orgq\x0bX\x04\x00\x00\x00pathq\x0cX\x0b\x00\x00\x00/robots.txtq\rX\x0c\x00\x00\x00last_checkedq\x0eGA\xd8\x87\xf5\xdc\xab\xd5\x00ub."
    )
    my_urls.store_rules("https://example.org", rules)
    assert my_urls.get_rules("http://test.org") is None
    assert my_urls.urldict["https://example.org"].rules is not None
    assert (
        my_urls.get_rules("https://example.org")
        == my_urls.urldict["https://example.org"].rules
        == rules
    )
    assert my_urls.get_crawl_delay("http://test.org", default=2) == 2
    assert my_urls.get_crawl_delay("https://example.org") == 5

    assert my_urls.compressed is False
    my_urls.urldict["https://example.org"].rules = None

    my_urls.compressed = True
    my_urls.store_rules("https://example.org", rules)
    assert my_urls.urldict["https://example.org"].rules is not None
    # no identity check since different location after compression
    assert my_urls.get_rules("https://example.org").mtime() == rules.mtime()
    my_urls.compressed = False

    # filters
    my_urls = UrlStore(language="en", strict=True)
    candidates = [
        "https://de.wikipedia.org/",
        "https://www.sitemaps.org/en_GB/protocol.html",
        "http://example.com/de/test.html",
    ]
    my_urls.add_urls(candidates)
    assert len(my_urls.urldict) == 1 and "https://www.sitemaps.org" in my_urls.urldict
    my_urls.add_urls(
        ["https://www.sitemaps.org/es/1"], appendleft=["https://www.sitemaps.org/fi/2"]
    )
    assert len(my_urls.urldict["https://www.sitemaps.org"].tuples) == 1

    # try example URLs
    example_domain = "https://www.example.org"
    example_urls = [f"{example_domain}/{str(a)}" for a in range(10000)]
    test_urls = [f"https://test.org/{str(uuid.uuid4())[:20]}" for _ in range(10000)]
    urls = example_urls + test_urls

    # compression 1
    my_urls = UrlStore(compressed=True)
    url_buffer = UrlStore()._buffer_urls(example_urls)
    my_urls.add_urls(example_urls)
    assert my_urls.total_url_number() == len(example_urls)
    # necessary to pickle
    my_urls._lock = None
    assert len(pickle.dumps(my_urls)) < len(pickle.dumps(url_buffer))
    assert my_urls.is_known(f"{example_domain}/100") is True
    # compression 2
    my_urls = UrlStore(compressed=True)
    url_buffer = UrlStore()._buffer_urls(test_urls)
    my_urls.add_urls(test_urls)
    assert my_urls.total_url_number() == len(test_urls)
    # necessary to pickle
    my_urls._lock = None
    assert len(pickle.dumps(my_urls)) < len(pickle.dumps(url_buffer))

    # test loading
    url_buffer = UrlStore()._buffer_urls(urls)
    assert sum(len(v) for _, v in url_buffer.items()) == len(urls)
    my_urls = UrlStore()
    my_urls.add_urls(urls)
    assert sum(len(my_urls._load_urls(k)) for k, _ in my_urls.urldict.items()) == len(
        urls
    )
    assert my_urls.total_url_number() == len(urls)
    assert my_urls.get_all_counts() == [0, 0]

    if my_urls.compressed is False:
        assert sum(len(v.tuples) for _, v in my_urls.urldict.items()) == len(urls)
    my_urls.add_urls(["https://visited.com/visited"], visited=True)
    assert my_urls.urldict["https://visited.com"].tuples[0].visited is True
    assert my_urls.urldict["https://visited.com"].all_visited is True
    assert my_urls.is_exhausted_domain("https://visited.com") is True
    # new unvisited URLs
    my_urls.add_urls(["https://visited.com/1"], visited=False)
    assert my_urls.urldict["https://visited.com"].tuples[1].visited is False
    assert my_urls.urldict["https://visited.com"].all_visited is False
    assert my_urls.is_exhausted_domain("https://visited.com") is False
    with pytest.raises(KeyError):
        assert my_urls.is_exhausted_domain("https://visited2.com") is True
    # revert changes for further tests
    del my_urls.urldict["https://visited.com"].tuples[1]
    my_urls.urldict["https://visited.com"].all_visited = True

    # test extension
    extension_urls = [f"{example_domain}/1/{str(a)}" for a in range(10)]
    my_urls.add_urls(extension_urls)
    assert len(my_urls._load_urls(example_domain)) == len(example_urls) + 10
    # test extension + deduplication
    extension_urls = [f"{example_domain}/1/{str(a)}/" for a in range(11)]
    my_urls.add_urls(appendleft=extension_urls)
    url_tuples = my_urls._load_urls(example_domain)
    assert len(url_tuples) == len(example_urls) + 11
    assert url_tuples[-1].urlpath == "/1/9" and url_tuples[0].urlpath == "/1/10/"

    # duplicates
    my_urls.add_urls(extension_urls)
    my_urls.add_urls(appendleft=extension_urls)
    assert len(my_urls._load_urls(example_domain)) == len(example_urls) + len(
        extension_urls
    )
    assert url_tuples[-1].urlpath == "/1/9" and url_tuples[0].urlpath == "/1/10/"

    # get_url
    assert my_urls.urldict[example_domain].timestamp is None
    assert my_urls.urldict[example_domain].count == 0

    url1 = my_urls.get_url(example_domain)
    timestamp = my_urls.urldict[example_domain].timestamp
    url2 = my_urls.get_url(example_domain)
    assert url1 != url2 and url1 == "https://www.example.org/1/10/"
    assert my_urls.urldict[example_domain].count == 2
    assert timestamp != my_urls.urldict[example_domain].timestamp
    assert url2 not in set(my_urls.find_unvisited_urls(example_domain))
    assert my_urls.get_all_counts() == [2, 0, 0]

    # as_visited=False
    timestamp = my_urls.urldict[example_domain].timestamp
    url3 = my_urls.get_url(example_domain, as_visited=False)
    assert url3 != url1 and url3 != url2
    assert my_urls.urldict[example_domain].count == 2
    assert timestamp == my_urls.urldict[example_domain].timestamp
    assert url3 in set(my_urls.find_unvisited_urls(example_domain))

    url_tuples = my_urls._load_urls(example_domain)
    # positions
    assert url1.endswith(url_tuples[0].urlpath) and url2.endswith(url_tuples[1].urlpath)
    # timestamp
    assert my_urls.urldict[example_domain].timestamp is not None
    # nothing left
    assert my_urls.urldict[example_domain].all_visited is False
    my_urls.add_urls(["http://tovisit.com/page"])
    assert my_urls.get_url("http://tovisit.com") == "http://tovisit.com/page"
    assert my_urls.urldict["http://tovisit.com"].all_visited is True
    assert my_urls.get_url("http://tovisit.com") is None

    # known domains
    assert my_urls.get_known_domains() == [
        "https://www.example.org",
        "https://test.org",
        "https://visited.com",
        "http://tovisit.com",
    ]

    # known or not
    assert my_urls.is_known("http://tovisit.com/page") is True
    assert my_urls.is_known("https://www.other.org/1") is False
    assert my_urls.is_known("https://www.example.org/1") is True
    candidates = [
        "https://test.org/category/this",
        "https://www.example.org/1",
        "https://otherdomain.org/",
    ]
    assert my_urls.filter_unknown_urls(candidates) == [
        "https://test.org/category/this",
        "https://otherdomain.org/",
    ]
    # visited or not
    assert (
        url_tuples[0].visited is True
        and url_tuples[1].visited is True
        and url_tuples[2].visited is False
    )
    assert my_urls.has_been_visited("http://tovisit.com/page") is True
    assert my_urls.urldict["http://tovisit.com"].all_visited is True
    assert my_urls.filter_unvisited_urls(["http://tovisit.com/page"]) == []
    assert my_urls.filter_unvisited_urls(["http://tovisit.com/otherpage"]) == [
        "http://tovisit.com/otherpage"
    ]
    assert my_urls.has_been_visited("https://www.other.org/1") is False
    assert my_urls.has_been_visited(url1) is True
    assert my_urls.has_been_visited(f"{example_domain}/this") is False
    assert my_urls.has_been_visited(f"{example_domain}/999") is False
    candidates = [url1, f"{example_domain}/this", f"{example_domain}/999"]
    assert my_urls.filter_unvisited_urls(candidates) == [
        example_domain + "/this",
        example_domain + "/999",
    ]
    assert (
        len(my_urls.find_known_urls(example_domain))
        == len(my_urls._load_urls(example_domain))
        == 10011
    )
    assert len(my_urls.find_unvisited_urls(example_domain)) == 10009
    assert my_urls.unvisited_websites_number() == 4

    # get download URLs
    downloadable_urls = my_urls.get_download_urls(timelimit=0)
    assert (
        len(downloadable_urls) == 2
        and downloadable_urls[0] == "https://www.example.org/1"
    )
    assert (
        datetime.now() - my_urls.urldict["https://www.example.org"].timestamp
    ).total_seconds() < 0.25
    assert my_urls.urldict["https://www.example.org"].count == 3
    assert my_urls.urldict["https://test.org"].count == 1
    downloadable_urls = my_urls.get_download_urls()  # limit=10
    assert len(downloadable_urls) == 0
    other_store = UrlStore()
    downloadable_urls = other_store.get_download_urls()
    assert downloadable_urls == [] and other_store.done is True

    # schedule
    schedule = other_store.establish_download_schedule()
    assert schedule == []
    # store exhaustion
    other_store = UrlStore()
    other_store.add_urls(
        ["http://domain.fi/page1", "http://domain.fi/page2", "http://domain.no/0"]
    )
    schedule = other_store.establish_download_schedule()
    assert len(schedule) == 3
    # reaching buffer limit
    schedule = my_urls.establish_download_schedule(max_urls=1, time_limit=1)
    assert (
        len(schedule) == 1
        and round(schedule[0][0]) == 1
        and schedule[0][1] == "https://www.example.org/2"
    )
    schedule = my_urls.establish_download_schedule(max_urls=6, time_limit=1)
    assert len(schedule) == 6 and round(max(s[0] for s in schedule)) == 4
    assert my_urls.urldict["https://www.example.org"].count == 7
    assert (
        my_urls.urldict["https://test.org"].count
        == 4
        == sum(u.visited is True for u in my_urls.urldict["https://test.org"].tuples)
    )
    assert my_urls.download_threshold_reached(8) is False
    assert my_urls.download_threshold_reached(7) is True


def test_dbdump(capsys):
    "Test cases where the URLs are dumped or printed."

    # database dump
    first_one = UrlStore()
    first_one.add_urls(["http://example.org/print", "http://print.org/print"])
    assert len(first_one.dump_urls()) == 2

    # database print out
    other_one = UrlStore()
    other_one.add_urls(["http://test.org/this"])
    other_one.print_urls()
    captured = capsys.readouterr()
    assert captured.out.strip() == "http://test.org/this\tFalse"

    # dump unvisited, don't test it on Windows
    if os.name != "nt":
        # standard
        interrupted_one = UrlStore()
        interrupted_one.add_urls(["https://www.test.org/1", "https://www.test.org/2"])
        # sys.exit() since signals are not caught
        with pytest.raises(SystemExit):
            sys.exit(1)
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
        # verbose
        interrupted_one = UrlStore(verbose=True)
        interrupted_one.add_urls(["https://www.test.org/1", "https://www.test.org/2"])
        # SIGINT + SIGTERM caught
        pid = os.getpid()
        with pytest.raises(SystemExit):
            os.kill(pid, signal.SIGINT)
        captured = capsys.readouterr()
        assert captured.out.strip().endswith("https://www.test.org/2")
