#!/usr/bin/python3

### Code made available on https://github.com/adbar/url-tools under GPL license.
### (C) Adrien Barbaresi, 2016.

# Purpose: filter a URL list and select a random subset of n URLs per domain name


import argparse
from collections import defaultdict
from random import sample
from urllib.parse import urlparse
import validators


parser = argparse.ArgumentParser()
parser.add_argument('-i', '--inputfile', dest='inputfile', help='input file', required=True)
parser.add_argument('-o', '--outputfile', dest='outputfile', help='output file', required=True)
parser.add_argument('-s', '--size', dest='size', help='sample size', type=int, default=1000)
parser.add_argument('-v', '--verbose', dest='verbose', help='verbose mode', action='store_true')
args = parser.parse_args()


urls = defaultdict(list)
urlbuffer = list()
lastseen = None

with open(args.inputfile, 'r', encoding='utf-8') as inputfh:
    with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
        for line in inputfh:
            parsed_url = urlparse(line.strip())

            # validate (https://github.com/gruns/furl ?)
            if bool(parsed_url.scheme) is False or len(parsed_url.netloc) < 5:
                continue
            if parsed_url.scheme != 'http' and parsed_url.scheme != 'https':
                continue
            if validators.url(parsed_url.geturl()) is False:
                continue

            # initial
            if lastseen is None:
                lastseen = parsed_url.netloc
            # key = r.scheme + '://' + r.netloc
            value = parsed_url.geturl()
            # continue collection
            if parsed_url.netloc == lastseen:
                # urls[key].append(value)
                urlbuffer.append(value)
            # sample, drop, start new collection
            else:
                if len(urlbuffer) <= args.size:
                    for item in urlbuffer:
                        outputfh.write(item + '\n')
                    if args.verbose is True:
                        print (lastseen, '\t\turls:', len(urlbuffer))
                else:
                    for item in sample(urlbuffer, args.size):
                        outputfh.write(item + '\n')
                    if args.verbose is True:
                        print (lastseen, '\t\turls:', len(urlbuffer), '\tprop.:', args.size/len(urlbuffer))

                urlbuffer = []
                urlbuffer.append(value)

            lastseen = parsed_url.netloc
