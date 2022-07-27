"""
Implements a basic command-line interface.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import argparse
import sys

from typing import Any, List

from .core import check_url, sample_urls


def parse_args(args: Any) -> Any:
    """Define parser for command-line arguments"""
    argsparser = argparse.ArgumentParser(
        description="Command-line interface for Courlan"
    )
    group1 = argsparser.add_argument_group("I/O", "Manage input and output")
    group1.add_argument(
        "-i",
        "--inputfile",
        help="name of input file (required)",
        type=str,
        required=True,
    )
    group1.add_argument(
        "-o",
        "--outputfile",
        help="name of output file (required)",
        type=str,
        required=True,
    )
    group1.add_argument(
        "-d",
        "--discardedfile",
        help="name of file to store discarded URLs (optional)",
        type=str,
    )
    group1.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    group2 = argsparser.add_argument_group("Filtering", "Configure URL filters")
    group2.add_argument(
        "--strict", help="perform more restrictive tests", action="store_true"
    )
    group2.add_argument(
        "-l", "--language", help="use language filter (ISO 639-1 code)", type=str
    )
    group2.add_argument(
        "-r", "--redirects", help="check redirects", action="store_true"
    )
    group3 = argsparser.add_argument_group(
        "Sampling", "Use sampling by host, configure sample size"
    )
    group3.add_argument("--sample", help="use sampling", action="store_true")
    group3.add_argument(
        "--samplesize", help="size of sample per domain", type=int, default=1000
    )
    group3.add_argument(
        "--exclude-max", help="exclude domains with more than n URLs", type=int
    )  # default=10000
    group3.add_argument(
        "--exclude-min", help="exclude domains with less than n URLs", type=int
    )
    return argsparser.parse_args()


def process_args(args: Any) -> None:
    """Start processing according to the arguments"""
    if not args.sample:
        with open(
            args.inputfile, "r", encoding="utf-8", errors="ignore"
        ) as inputfh, open(args.outputfile, "w", encoding="utf-8") as outputfh:
            for line in inputfh:
                result = check_url(
                    line,
                    strict=args.strict,
                    with_redirects=args.redirects,
                    language=args.language,
                )
                if result is not None:
                    outputfh.write(result[0] + "\n")
                # proceed with discarded URLs. to be rewritten
                elif args.discardedfile is not None:
                    with open(args.discardedfile, "a", encoding="utf-8") as discardfh:
                        discardfh.write(line)
    else:
        urllist: List[str] = []
        with open(args.inputfile, "r", encoding="utf-8", errors="ignore") as inputfh:
            urllist.extend(line.strip() for line in inputfh)
        with open(args.outputfile, "w", encoding="utf-8") as outputfh:
            for url in sample_urls(
                urllist,
                args.samplesize,
                exclude_min=args.exclude_min,
                exclude_max=args.exclude_max,
                strict=args.strict,
                verbose=args.verbose,
            ):
                outputfh.write(url + "\n")


def main() -> None:
    """Run as a command-line utility."""
    args = parse_args(sys.argv[1:])
    process_args(args)


if __name__ == "__main__":
    main()
