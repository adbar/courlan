"""
Implements a basic command-line interface.
"""

## This file is available from https://github.com/adbar/urltools

import argparse
import sys

from .core import urlcheck


def parse_args(args):
    """Define parser for command-line arguments"""
    argsparser = argparse.ArgumentParser()
    argsparser.add_argument("-v", "--verbose",
                            help="increase output verbosity",
                            action="store_true")
    argsparser.add_argument("-i", "--inputfile",
                            help="""name of input file""",
                            type=str, required=True)
    argsparser.add_argument("-o", "--outputfile",
                            help="""name of input file""",
                            type=str, required=True)
    return argsparser.parse_args()


def main():
    """Run as a command-line utility."""
    # arguments
    args = parse_args(sys.argv[1:])
    with open(args.inputfile, 'r', encoding='utf-8', errors='ignore') as inputfh:
        with open(args.outputfile, 'w', encoding='utf-8') as outputfh:
            for line in inputfh:
                result = urlcheck(line, False)
                if result is not None:
                    outputfh.write(result[0] + '\n')


if __name__ == '__main__':
    main()
