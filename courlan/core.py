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
    SITE_DATES,
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
from .hosts import _compared_host
from .network import redirection_test
from .settings import BLACKLIST
from .urlutils import (
    decode_entities,
    fix_relative_urls,
    get_base_url,
    get_tldinfo,
    is_known_link,
)

LOGGER = logging.getLogger(__name__)

FIND_LINKS_REGEX = re.compile(r"<a\s+[^<>]+?>", re.I)
# attributes, also glued after a quote, not data-href, :href or a "/hreflang-guide" path
HREFLANG_REGEX = re.compile(r"""(?<![\w:-])hreflang\s*=\s*["']?([a-z-]+)""", re.I)
# quoted values keep their spaces and end at any quote, as script-built
# anchors hold the other one: href="#' + id + '"
LINK_REGEX = re.compile(
    r"""(?<![\w:-])href\s*=\s*(?:["']([^"'>]*)|([^\s"'>]+))""", re.I
)
NOFOLLOW_REGEX = re.compile(
    r"""(?<![\w:-])rel\s*=\s*(?:"[^"]*?|'[^']*?|[^\s"'>]*?)\bnofollow\b""", re.I
)


@lru_cache(maxsize=4096)
def _host_parts(
    scheme: str, netloc: str
) -> tuple[str, str, str | None, str | None] | None:
    """Return the normalized scheme and host, and the domain label and name
    of a netloc without userinfo, or None if the host is unsuitable."""
    scheme, _, host = normalize_netloc_parts(SplitResult(scheme, netloc, "", "", ""))
    # domain_filter expects host[:port]
    if not host or domain_filter(host) is False:
        return None
    label, domain = get_tldinfo(f"{scheme}://{host}")
    return scheme, host, label, domain


def _file_path(path: str, trailing_slash: bool) -> str:
    """Return the path whose extension counts: the one of an embedded URL
    (Wayback Machine), without the slashes that rebuild_url strips."""
    if "://" in path:
        path = path.rpartition("://")[2].partition("/")[2]
    return path if trailing_slash else path.rstrip("/")


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
        # clean
        url = scrub_url(url)

        # length test
        if basic_filter(url) is False:
            raise ValueError("basic filter")

        # get potential redirect, can raise ValueError
        if with_redirects:
            url = redirection_test(url)

        # split and validate
        _, parsed_url = validate_url(url)
        if parsed_url is None:
            raise ValueError("validation test")

        # unsuitable domain/host name, userinfo is dropped before the cache
        hostinfo = _host_parts(parsed_url.scheme, parsed_url.netloc.rpartition("@")[2])
        if hostinfo is None:
            raise ValueError("domain name")
        scheme, host, label, domain = hostinfo

        # links on the unwanted side are dropped before the path work
        if external is not None and external != (label != ref_label):
            return None

        # normalized parts, shared with the rebuild; the query comes last as
        # it is the expensive one and the filters below may reject first
        path = normalize_path(parsed_url.path)

        # content filter based on extensions
        if extension_filter(_file_path(path, trailing_slash)) is False:
            raise ValueError("extension filter")

        # spam & structural elements, also hidden in the query or the fragment
        pre_normalized = url
        if type_filter(url, strict=strict, with_nav=with_nav) is False:
            raise ValueError("type filter")
        # dates need the slash that rebuild_url strips
        if (
            not trailing_slash
            and path[-1:] == "/"
            and SITE_DATES.search(f"{host}{path}")
            and not (with_nav and is_navigation_page(url))
        ):
            raise ValueError("type filter")

        query = clean_query(parsed_url.query, strict, language)

        # strict content filtering: the query has to be the one that survives
        # normalization, else a stripped param keeps an index page that
        # check_url would reject on a second pass
        if strict and path_filter(path, query) is False:
            raise ValueError("path filter")

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
            raise ValueError("type filter")

        # internationalization and language heuristics in URL
        if (
            language is not None
            and lang_filter(url, language, strict, trailing_slash) is False
        ):
            raise ValueError("lang filter")

        # domain info: use blacklist in strict mode only
        if not domain or (strict and (label in BLACKLIST or domain in BLACKLIST)):
            raise ValueError("domain name")

    except (AttributeError, ValueError) as err:
        # the step that rejected the URL, the language param or the network
        reason = err.args[0] if isinstance(err, ValueError) and err.args else "input"
        LOGGER.debug("rejected, %s: %s", reason, url)
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
) -> list[str]:
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
        A list of filtered HTTP links checked for sanity and consistency,
        in document order.

    Raises:
        ValueError: if the deprecated 'base_url' argument is provided.
    """
    if base_url:
        raise ValueError("'base_url' is deprecated, use 'url' instead.")

    base_url = get_base_url(url or "")
    url = url or base_url
    if not pagecontent:
        return []
    # document order, so that the first variant of a link wins
    candidates: dict[str, None] = {}
    validlinks: dict[str, None] = {}

    # define host reference
    reference = reference or base_url
    ref_label = _compared_host(get_tldinfo(reference)[0]) if reference else None

    # extract links
    for link in (m[0] for m in FIND_LINKS_REGEX.finditer(pagecontent)):
        # cheap gate first, "nofollow" and "NOFOLLOW" alike
        if ("ollow" in link or "OLLOW" in link) and NOFOLLOW_REGEX.search(link):
            continue
        # https://en.wikipedia.org/wiki/Hreflang
        if (
            no_filter is False
            and language is not None
            and "hreflang" in link
            and (langmatch := HREFLANG_REGEX.search(link))
            and not (
                (lang := langmatch[1].lower()).startswith(language)
                or lang == "x-default"
            )
        ):
            continue
        linkmatch = LINK_REGEX.search(link)
        if linkmatch:
            href = linkmatch[linkmatch.lastindex]  # type: ignore[index]
            # inner spaces are encoded as browsers do, scrub_url would join them
            candidates[decode_entities(href).strip().replace(" ", "%20")] = None

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
        validlinks[link] = None

    LOGGER.info("%s links found – %s valid links", len(candidates), len(validlinks))
    return list(validlinks)


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
