#!/usr/bin/python3

### Code made available on https://github.com/adbar/url-tools under GPL license.
### (C) Adrien Barbaresi, 2016.

# Purpose: filter a URL list and select a random subset of n URLs per domain name
## takes a sorted URL list as input!


import argparse
from collections import defaultdict
from functools import cmp_to_key
import locale
from random import sample
import sys
from urllib.parse import urlparse
import validators # https://github.com/kvesteri/validators


parser = argparse.ArgumentParser()
parser.add_argument('-i', '--inputfile', dest='inputfile', help='input file', required=True)
parser.add_argument('-o', '--outputfile', dest='outputfile', help='output file', required=True)
parser.add_argument('-s', '--size', dest='size', help='size of sample per domain', type=int, default=1000)
parser.add_argument('-v', '--verbose', dest='verbose', help='verbose mode', action='store_true')
parser.add_argument('--nowarnings', dest='nowarnings', help='disable sort warnings', action='store_true')
parser.add_argument('--excludesize', dest='excludesize', help='exclude domains with more than n URLs', type=int) # default=10000
args = parser.parse_args()


urls = defaultdict(list)
urlbuffer = list()
lastseen = None
locale.setlocale(locale.LC_ALL, "")


# classify on the fly
with open(args.inputfile, 'r', encoding='utf-8', errors='ignore') as inputfh:
    with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
        for line in inputfh:
            # use standard parsing library
            parsed_url = urlparse(line.strip())

            # validate (https://github.com/gruns/furl ?)
            if bool(parsed_url.scheme) is False or len(parsed_url.netloc) < 5:
                continue
            if parsed_url.scheme != 'http' and parsed_url.scheme != 'https':
                continue
            if validators.url(parsed_url.geturl()) is False:
                continue

            # initialize
            if lastseen is None:
                lastseen = parsed_url.netloc

            # dump URL
            url = parsed_url.geturl()

            ## continue collection
            if parsed_url.netloc == lastseen:
                urlbuffer.append(url)

            ## sample, drop, fresh start
            else:
                # test if sorted
                if args.nowarnings is False:
                    testlist = [lastseen, parsed_url.netloc]
                    sortedtest = sorted(testlist, key=cmp_to_key(locale.strcoll))
                    if sortedtest[0] != testlist[0]:
                        sys.exit('input list not sorted, exiting.')

                # write all the buffer
                if len(urlbuffer) <= args.size:
                    for item in urlbuffer:
                        outputfh.write(item + '\n')
                    if args.verbose is True:
                        print (lastseen, '\t\turls:', len(urlbuffer))
                # or sample URLs
                else:
                    # threshold for large websites
                    if args.excludesize is None or len(urlbuffer) <= args.excludesize:
                        for item in sample(urlbuffer, args.size):
                            outputfh.write(item + '\n')
                        if args.verbose is True:
                            print (lastseen, '\t\turls:', len(urlbuffer), '\tprop.:', args.size/len(urlbuffer))
                    else:
                        if args.verbose is True:
                            print ('discarded (exclude size):', lastseen, '\t\turls:', len(urlbuffer))

                urlbuffer = []
                urlbuffer.append(url)

            lastseen = parsed_url.netloc
