"""
Implements a basic command-line interface.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import argparse
import sys

from .core import check_url, sample_urls


def parse_args(args):
    """Define parser for command-line arguments"""
    argsparser = argparse.ArgumentParser()
    argsparser.add_argument("-i", "--inputfile",
                            help="""name of input file""",
                            type=str, required=True)
    argsparser.add_argument("-o", "--outputfile",
                            help="""name of input file""",
                            type=str, required=True)
    argsparser.add_argument("-v", "--verbose",
                            help="increase output verbosity",
                            action="store_true")
    argsparser.add_argument("-l", "--language",
                            help="use language filter",
                            action="store_true")
    argsparser.add_argument("-r", "--redirects",
                            help="check redirects",
                            action="store_true")
    argsparser.add_argument('-s', '--sample',
                            help='use sampling',
                            action="store_true")
    argsparser.add_argument('--samplesize',
                            help='size of sample per domain',
                            type=int, default=1000)
    argsparser.add_argument('--exclude-max',
                            help='exclude domains with more than n URLs',
                            type=int) # default=10000
    argsparser.add_argument('--exclude-min',
                            help='exclude domains with less than n URLs',
                            type=int)
    return argsparser.parse_args()


def main():
    """Run as a command-line utility."""
    # arguments
    args = parse_args(sys.argv[1:])
    if args.sample is False:
        with open(args.inputfile, 'r', encoding='utf-8', errors='ignore') as inputfh:
            with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
                for line in inputfh:
                    result = check_url(line, with_redirects=args.redirects, with_language=args.language)
                    if result is not None:
                        outputfh.write(result[0] + '\n')
    else:
        urllist = list()
        with open(args.inputfile, 'r', encoding='utf-8', errors='ignore') as inputfh:
            for line in inputfh:
                urllist.append(line.strip())
        with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
            for url in sample_urls(urllist, args.samplesize, exclude_min=args.exclude_min, exclude_max=args.exclude_max, verbose=args.verbose):
                outputfh.write(url + '\n')

if __name__ == '__main__':
    main()
