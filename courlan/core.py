"""
Core functions needed to make the module work.
"""

import logging
import re
from functools import lru_cache
from urllib.parse import SplitResult
from urllib.robotparser import RobotFileParser

from .clean import (
    clean_query,
    normalize_netloc_parts,
    normalize_path,
    rebuild_url,
    scrub_url,
)
from .filters import (
    basic_filter,
    domain_filter,
    extension_filter,
    is_navigation_page,
    is_not_crawlable,
    lang_filter,
    path_filter,
    type_filter,
    validate_url,
)
from .network import redirection_test
from .settings import BLACKLIST
from .urlutils import (
    _host_form,
    fix_relative_urls,
    get_base_url,
    get_tldinfo,
    is_known_link,
)

LOGGER = logging.getLogger(__name__)

FIND_LINKS_REGEX = re.compile(r"<a\s+[^<>]+?>", re.I)
HREFLANG_REGEX = re.compile(r'hreflang=["\']?([a-z-]+)', re.I)
# *? so empty href="" / href='' do not capture the closing quote as the URL
LINK_REGEX = re.compile(r'href=["\']?([^ ]*?)(["\' >])', re.I)


@lru_cache(maxsize=4096)
def _host_parts(
    scheme: str, netloc: str
) -> tuple[str, str, str | None, str | None] | None:
    """Return the normalized scheme and host, without userinfo, and the domain
    label and name of a netloc, or None if the host is unsuitable."""
    scheme, _, host = normalize_netloc_parts(SplitResult(scheme, netloc, "", "", ""))
    # domain_filter expects host[:port]
    if not host or domain_filter(host) is False:
        return None
    label, domain = get_tldinfo(f"{scheme}://{host}")
    return scheme, host, label, domain


def check_url(
    url: str,
    strict: bool = False,
    with_redirects: bool = False,
    language: str | None = None,
    with_nav: bool = False,
    trailing_slash: bool = True,
) -> tuple[str, str] | None:
    """Check links for appropriateness and sanity

    Args:
        url: url to check
        strict: set to True for stricter filtering
        with_redirects: set to True for redirection test (per HTTP HEAD request)
        language: set target language (ISO 639-1 codes)
        with_nav: set to True to include navigation pages instead of discarding them
        trailing_slash: preserve trailing slashes (default True); when
            False, strip them from paths without a query string. With the
            default True and strict=False, a bare root slash is only kept
            when a query or fragment follows it, otherwise it is stripped

    Returns:
        A tuple consisting of canonical URL and extracted domain

    Raises:
        Nothing: invalid URLs are caught internally and None is returned.
    """
    return _check_url(url, strict, with_redirects, language, with_nav, trailing_slash)


def _check_url(
    url: str,
    strict: bool,
    with_redirects: bool,
    language: str | None,
    with_nav: bool,
    trailing_slash: bool,
    external: bool | None = None,
    ref_label: str | None = None,
) -> tuple[str, str] | None:
    """check_url, plus an early host gate: with external set, keep only the links
    on that side of the reference domain label, as is_external would."""
    # scrub, parse and normalize, then filter on the normalized parts
    # and the final form so the output is a fixed point
    try:
        # length test
        if basic_filter(url) is False:
            raise ValueError

        # clean
        url = scrub_url(url)

        # get potential redirect, can raise ValueError
        if with_redirects:
            url = redirection_test(url)

        # split and validate
        _, parsed_url = validate_url(url)
        if parsed_url is None:
            raise ValueError

        # unsuitable domain/host name, userinfo is dropped from the output
        hostinfo = _host_parts(parsed_url.scheme, parsed_url.netloc)
        if hostinfo is None:
            raise ValueError
        scheme, host, label, domain = hostinfo

        # links on the unwanted side are dropped before the path work
        if external is not None and external != (_host_form(label) != ref_label):
            return None

        # normalized parts, shared with the rebuild; the query comes last as
        # it is the expensive one and the filters below may reject first
        path = normalize_path(parsed_url.path)

        # content filter based on extensions
        if extension_filter(path) is False:
            raise ValueError

        # spam & structural elements, also hidden in the query or the fragment
        pre_normalized = url
        if type_filter(url, strict=strict, with_nav=with_nav) is False:
            raise ValueError

        query = clean_query(parsed_url.query, strict, language)

        # strict content filtering: the query has to be the one that survives
        # normalization, else a stripped param keeps an index page that
        # check_url would reject on a second pass
        if strict and path_filter(path, query) is False:
            raise ValueError

        # rebuild
        url = rebuild_url(
            scheme,
            host,
            path,
            query,
            parsed_url.fragment,
            strict,
            language,
            trailing_slash,
        )

        # again if normalization changed the URL, it can create patterns of its own
        if (
            url != pre_normalized
            and type_filter(url, strict=strict, with_nav=with_nav) is False
        ):
            raise ValueError

        # internationalization and language heuristics in URL
        if (
            language is not None
            and lang_filter(url, language, strict, trailing_slash) is False
        ):
            raise ValueError

        # domain info: use blacklist in strict mode only
        if not domain or (strict and (label in BLACKLIST or domain in BLACKLIST)):
            return None

    except (AttributeError, ValueError):
        LOGGER.debug("discarded URL: %s", url)
        return None

    return url, domain


def extract_links(
    pagecontent: str,
    url: str | None = None,
    external_bool: bool = False,
    *,
    no_filter: bool = False,
    language: str | None = None,
    strict: bool = True,
    trailing_slash: bool = True,
    with_nav: bool = False,
    redirects: bool = False,
    reference: str | None = None,
    base_url: str | None = None,
) -> set[str]:
    """Filter links in a HTML document using a series of heuristics

    Args:
        pagecontent: whole page as a string
        url: full URL of the original page
        external_bool: set to True for external links only, False for
            internal links only
        no_filter: override settings and bypass checks to return all possible URLs
        language: set target language (ISO 639-1 codes)
        strict: set to True for stricter filtering
        trailing_slash: preserve trailing slashes (default True); when
            False, strip them from paths without a query string. With the
            default True and strict=False, a bare root slash is only kept
            when a query or fragment follows it, otherwise it is stripped
        with_nav: set to True to include navigation pages instead of discarding them
        redirects: set to True for redirection test (per HTTP HEAD request)
        reference: provide a host reference for external/internal evaluation

    Returns:
        A set containing filtered HTTP links checked for sanity and consistency.

    Raises:
        ValueError: if the deprecated 'base_url' argument is provided.
    """
    if base_url:
        raise ValueError("'base_url' is deprecated, use 'url' instead.")

    base_url = get_base_url(url or "")
    url = url or base_url
    # document order, so that the first variant of a link wins
    candidates: dict[str, None] = {}
    validlinks: set[str] = set()
    if not pagecontent:
        return validlinks

    # define host reference
    reference = reference or base_url
    ref_label = _host_form(get_tldinfo(reference)[0]) if reference else None

    # extract links
    for link in (m[0] for m in FIND_LINKS_REGEX.finditer(pagecontent)):
        if "rel=" in link and "nofollow" in link:
            continue
        # https://en.wikipedia.org/wiki/Hreflang
        if no_filter is False and language is not None and "hreflang" in link:
            langmatch = HREFLANG_REGEX.search(link)
            if langmatch and (
                (lang := langmatch[1].lower()).startswith(language)
                or lang == "x-default"
            ):
                linkmatch = LINK_REGEX.search(link)
                if linkmatch:
                    candidates[linkmatch[1]] = None
        # default
        else:
            linkmatch = LINK_REGEX.search(link)
            if linkmatch:
                candidates[linkmatch[1]] = None

    # filter candidates
    for link in candidates:
        # repair using base
        if not link.startswith("http"):
            try:
                link = fix_relative_urls(url, link)
            except ValueError:
                LOGGER.debug("unresolvable link: %s", link)
                continue
        # check
        if no_filter is False:
            # with the external/internal links filter
            checked = _check_url(
                link,
                strict,
                redirects,
                language,
                with_nav,
                trailing_slash,
                external_bool if reference else None,
                ref_label,
            )
            if checked is None:
                continue
            link = checked[0]
        if is_known_link(link, validlinks):
            continue
        validlinks.add(link)

    LOGGER.info("%s links found – %s valid links", len(candidates), len(validlinks))
    return validlinks


def filter_links(
    htmlstring: str,
    url: str | None,
    *,
    lang: str | None = None,
    rules: RobotFileParser | None = None,
    external: bool = False,
    strict: bool = False,
    with_nav: bool = True,
    base_url: str | None = None,
) -> tuple[list[str], list[str]]:
    "Find links in a HTML document, filter and prioritize them for crawling purposes."

    if base_url:
        raise ValueError("'base_url' is deprecated, use 'url' instead.")

    links, links_priority = [], []

    for link in extract_links(
        pagecontent=htmlstring,
        url=url,
        external_bool=external,
        language=lang,
        strict=strict,
        with_nav=with_nav,
    ):
        # sanity check
        if is_not_crawlable(link) or (
            rules is not None and not rules.can_fetch("*", link)
        ):
            continue
        # store
        if is_navigation_page(link):
            links_priority.append(link)
        else:
            links.append(link)

    return links, links_priority
