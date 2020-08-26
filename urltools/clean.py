
import logging
import re


def clean(url):
    # trim
    url = url.strip()
    # clean the input string
    url = url.replace('[ \t]+', '')
    # trailing slashes
    url = url.rstrip('/')
    # CDATA             # <![CDATA[http://www.urbanlife.de/item/260-bmw-i8-hybrid-revolution-unter-den-sportwagen.html]]>
    if url.startswith('<![CDATA['): # re.match(r'<!\[CDATA\[', url):
        url = url.replace('<![CDATA[', '') # url = re.sub(r'^<!\[CDATA\[', '', url)
        url = url.replace(']]>', '') # url = re.sub(r'\]\]>$', '', url)
    # &amp;
    if '&amp;' in url:
        url = url.replace('&amp;', '&')
    # double/faulty URLs
    protocols = re.findall(r'https?://', url)
    if len(protocols) > 1:
        logging.debug('double url: %s %s', len(protocols), url)
        match = re.match(r'https?://.+?(https?://.+?)(http|$)', url)
        if match:
            url = match.group(1)
            logging.debug('taking url: %s', url)
    # lower
    url = url.lower()
    return url

