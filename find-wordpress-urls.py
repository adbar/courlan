#!/usr/bin/python3
# -*- coding: utf-8 -*-

### Code made available on https://github.com/adbar/url-tools under GPL license.
### Adrien Barbaresi, 2015.

# Purpose: Extract possible WordPress links
# http://codex.wordpress.org/Using_Permalinks

## TODO:
# fasttrack: wordpress.com
# tests: nebojsaozimic potkozarje


from __future__ import print_function
from urllib.parse import urlparse
import re
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--inputfile', dest='inputfile', help='name of the input file', required=True)
parser.add_argument('-o', '--outputfile', dest='outputfile', help='name of the output file', required=True)
parser.add_argument('-l', '--lax', dest='lax', action="store_true", default=False, help='use lax patterns')
args = parser.parse_args()

start_time = time.time()
known_hosts = set()
i = 0
j = 0
k = 0
l = 0


# test if part of the URL is interesting
def find_target(url):
    # uparse = urlparse(url)

    # wordpress.com
    if re.match(r'https?://.+?\.wordpress\.[a-z]{2,3}', url): # [a-z]+?
       # files.wordpress.com hack
       url = re.sub(r'\.files\.wordpress\.', '.wordpress.', url)
       # wphost = re.match (r'(htt.+?\.wordpress\.[a-z]{2,3}/)', url)
       wphost = re.match (r'(htt.+?\.wordpress\.[a-z]{2,3})/?', url)
       if wphost:
           return wphost.group(1).rstrip('/') + '/'

    # K.O. victory
    ko_string = re.match(r'(.+?)(/wp/|/wordpress/|/wp-content/)', url)
    if ko_string:
        return ko_string.group(1).rstrip('/') + '/'

    # /tag/ /category/
    tagcat = re.match(r'(.+?)(/tag/|/category/|\?cat=)', url)
    if tagcat:
        return tagcat.group(1).rstrip('/') + '/'

    # query parameters
    if re.search(r'/\?p=|\?page_id=|\?paged=/', url):
        mquery = re.match(r'(https?://.+?/)(blog/|weblog/)?(\?p=|\?page_id=|\?paged=)', url)
        if mquery:
            if mquery.group(2) and mquery.group(3):
                return mquery.group(1) + mquery.group(2)
            else:
                return mquery.group(1).rstrip('/') + '/'

    # URL types
    if re.search(r'/20[0-9]{2}/[0-9]{2}/|/archives/', url):
        url_types = re.search(r'(https?://.+?/)(blog/|weblog/)?(20[0-9]{2}/[0-9]{2}/|/archives/)', url)
        if url_types:
            # print (url)
            if url_types.group(2) and url_types.group(3):
                return url_types.group(1) + url_types.group(2)
            else:
                return url_types.group(1).rstrip('/') + '/'

    # lax
    if args.lax is True:
    # path correction
    # mpath = re.match(r'(/blog/|/weblog/)', url) #uparse.path
    # if mpath:
    #    path = mpath.group(1)
    #else:
    #    path = '' 
        if re.search(r'/[a-z]+-[a-z]+-[a-z]+|/20[0-9]{2}/', url):
            url_lax = re.search(r'(https?://.+?/)(blog/|weblog/)?(/[a-z]+-[a-z]+-[a-z]+|/20[0-9]{2}/)', url)
            if url_lax:
                if url_lax.group(2) and url_lax.group(3):
                    return url_lax.group(1) + url_lax.group(2)
                else:
                    return url_lax.group(1).rstrip('/') + '/'

    return None

with open(args.inputfile, 'r', encoding='utf-8') as inputfh:
    with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
        # avoid errors (todo: solve)
        try:
            for url in inputfh:
                i += 1
                target = None
                # sanitize
                url = url.lower().rstrip('\n')

                # filters
                if re.match('http', url) and len(url) > 11:
                    # akamai/fbcdn, etc.
                    if not re.search(r'\.blogspot\.|\.google\.|\.tumblr\.|\.typepad\.com|\.wp\.com|\.archive\.|akamai|fbcdn|baidu\.com|\.gravatar\.', url):
                        # test if part of the URL is interesting
                        target = find_target(url)

                # limit path depth and filter out queries
                if target and not re.search(r'=|\.php', target) and len(re.findall(r'/', target)) <= 4:
                    # make sure the host name is fresh
                    normalize = re.search(r'https?://(www\.)?(.+?)/', target)
                    if normalize and normalize.group(2) not in known_hosts:
                    # if True:
                        known_hosts.add(normalize.group(2))
                        outputfh.write(target + '\n')
                        j += 1
        except UnicodeDecodeError:
            print ('Unicode error line', i + 1)


print ('# lines seen:\t\t', i)
print ('# results:\t\t', j)
exec_time = time.time() - start_time
print ('# exec time:\t\t{0:.2f}' . format(exec_time))
print ('# secs per success:\t{0:.2f}' . format(exec_time / j))
# print (k, l)
