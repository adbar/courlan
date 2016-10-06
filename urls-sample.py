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
import regex as re
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
parser.add_argument('--minsize', dest='minsize', help='exclude domains with less than n URLs', type=int)
args = parser.parse_args()


urls = defaultdict(list)
urlbuffer = set()
lastseen = None
if args.nowarnings is False:
    locale.setlocale(locale.LC_ALL, "")



def clean(url):
    # trim
    url = url.strip()
    # clean the input string
    url = url.replace('[ \t]+', '')
    match = re.search(r'^(https?://.+?)https?://.+?$', url)
    if match:
        url = match.group(1)
    return url


def validate(url):
    # validate (https://github.com/gruns/furl ?)
    if bool(parsed_url.scheme) is False or len(parsed_url.netloc) < 5:
        return False
    if parsed_url.scheme != 'http' and parsed_url.scheme != 'https':
        return False
    if validators.url(parsed_url.geturl()) is False:
        return False
    # default
    return True


def typefilter(url):
    # not suited and obvious extensions
    if re.search(r'^http://add?s?\.|^http://banner\.|doubleclick|tradedoubler\.com|livestream|live\.|videos?\.|feed$|rss$', url, re.IGNORECASE):
        return False
    if re.search(r'\.atom$|\.json$|\.css$|\.xml$|\.js$|\.jpg$|\.jpeg$|\.png$|\.gif$|\.tiff$|\.pdf$|\.ogg$|\.mp3$|\.m4a$|\.aac$|\.avi$|\.mp4$|\.mov$|\.webm$|\.flv$|\.ico$|\.pls$|\.zip$|\.tar$|\.gz$|\.iso$|\.swf$', url, re.IGNORECASE):
        return False
    if re.search(r'\.jpg[&?]|\.jpeg[&?]|\.png[&?]|\.gif[&?]|\.pdf[&?]|\.ogg[&?]|\.mp3[&?]|\.avi[&?]|\.mp4[&?]', url, re.IGNORECASE):
        return False
    # default
    return True


def spamfilter(url):
    # re.IGNORECASE flag or line.lower()
    if re.search(r'[\./_-](porno?|xxx|fick|arsch)', url, re.IGNORECASE) or re.search(r'(cams|cash|porno?|sex|xxx)[\./_-]', url,  re.IGNORECASE) or re.search(r'gangbang|incest|erotik|sexy', url, re.IGNORECASE) or re.search(r'[\./_-](adult|ass|sex|cam)[\./_-]', url,  re.IGNORECASE):
        return False
    # default
    return True



# Open and load spam-list file, if there is one
#if args.spamlistfile is not None:
#    filename = options.spamlistfile
#    if args.path is not None:
#       filename = options.path + filename
#    try:
#        spamlistfile = open(filename, 'r')
#        spamset = set()
#        # there should be domains names in the file
#        for domain in spamlistfile:
#            domain = domain.rstrip()
#            spamset.add(domain)
#        spamlistfile.close()
#        # '{} format' not supported before Python 2.7
#        try:
#            print('Length of the spam list: {:,}' . format(len(spamset)))
#        except ValueError:
 #           print('Length of the spam list:', len(spamset))
 #   except IOError:
#        print('Could not open the file containing the spam reference list:', options.spamlistfile, '\nThe URLs will not be checked for spam.')
#else:
#    print('No spam reference list given, the URLs will not be checked for spam.')


# fall-back if there is nowhere to write the urls seen as spam
#if options.spamurls is None:
#    options.spamurls = options.inputfile + '_spam-detected-urls'
#    print('No file name given for the urls classified as spam, defaulting to', options.spamurls)







# classify on the fly
with open(args.inputfile, 'r', encoding='utf-8', errors='ignore') as inputfh:
    with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
        for line in inputfh:

            # first basic filter
            if not re.match('https?://', line):
                continue

            # clean
            url = clean(line)

            # use standard parsing library
            try:
                parsed_url = urlparse(url)
            except ValueError:
                continue

            # validate
            if validate(parsed_url) is False:
                continue
            if typefilter(url) is False:
                continue
            if spamfilter(url) is False:
                continue

            # initialize
            if lastseen is None:
                lastseen = parsed_url.netloc

            # dump URL
            # url = parsed_url.geturl()

            ## continue collection
            if parsed_url.netloc == lastseen:
                urlbuffer.add(url)

            ## sample, drop, fresh start
            else:
                # test if sorted
                if args.nowarnings is False:
                    testlist = [lastseen, parsed_url.netloc]
                    sortedtest = sorted(testlist, key=cmp_to_key(locale.strcoll))
                    if sortedtest[0] != testlist[0]:
                        sys.exit('input list not sorted, exiting.')

                # threshold for too small websites
                if args.minsize is None or len(urlbuffer) >= args.minsize:

                    # write all the buffer
                    if len(urlbuffer) <= args.size:
                        for item in urlbuffer:
                            outputfh.write(item + '\n')
                        if args.verbose is True:
                            print (lastseen, '\t\turls:', len(urlbuffer))
                    # or sample URLs
                    else:
                        # threshold for too large websites
                        if args.excludesize is None or len(urlbuffer) <= args.excludesize:
                            for item in sample(urlbuffer, args.size):
                                outputfh.write(item + '\n')
                            if args.verbose is True:
                                print (lastseen, '\t\turls:', len(urlbuffer), '\tprop.:', args.size/len(urlbuffer))
                        else:
                            if args.verbose is True:
                                print ('discarded (exclude size):', lastseen, '\t\turls:', len(urlbuffer))
                else:
                    if args.verbose is True:
                        print ('discarded (exclude size):', lastseen, '\t\turls:', len(urlbuffer))

                urlbuffer = set()
                urlbuffer.add(url)

            lastseen = parsed_url.netloc




# print final results
## http://docs.python.org/library/string.html#format-specification-mini-language
#try:
#    print('Total URLs seen: {:,}' . format(total_urls))
#    print('Total URLs dropped: {:,}' . format(dropped_urls))
#    print('Ratio: {0:.2f}' . format((dropped_urls/total_urls)*100), '%')
## '{} format' not supported before Python 2.7
#except ValueError:
#    print('Total URLs seen:', total_urls)
#    print('Total URLs dropped:', dropped_urls)    #'Total URLs dropped: %d'
#    print('Ratio:', ((dropped_urls/total_urls)*100), '%')    #'Ratio: %.02f'

