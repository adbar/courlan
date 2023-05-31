"""
Implements a basic command-line interface.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license

import argparse
import sys

from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import islice
from typing import Any, Iterator, List, Optional, Tuple

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
    group1.add_argument(
        "-p",
        "--parallel",
        help="number of parallel processes (not used for sampling)",
        type=int,
        default=4,
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


def _cli_check_urls(
    urls: List[str],
    strict: bool = False,
    with_redirects: bool = False,
    language: Optional[str] = None,
    with_nav: bool = False,
) -> List[Tuple[bool, str]]:
    "Internal function to be used with CLI multiprocessing."
    results = []
    for url in urls:
        result = check_url(
            url,
            strict=strict,
            with_redirects=with_redirects,
            language=language,
            with_nav=with_nav,
        )
        if result is not None:
            results.append((True, result[0]))
        else:
            results.append((False, url))
    return results


def _get_line_batches(filename: str, size: int = 1000) -> Iterator[List[str]]:
    "Iterate over a file and returns series of line batches."
    with open(filename, "r", encoding="utf-8", errors="ignore") as inputfh:
        while True:
            line_batch = list(islice(inputfh, size))
            if not line_batch:
                break
            yield line_batch


def process_args(args: Any) -> None:
    """Start processing according to the arguments"""
    if not args.sample:
        with ProcessPoolExecutor(max_workers=args.parallel) as executor, open(
            args.outputfile, "w", encoding="utf-8"
        ) as outputfh:
            futures = (
                executor.submit(
                    _cli_check_urls,
                    batch,
                    strict=args.strict,
                    with_redirects=args.redirects,
                    language=args.language,
                )
                for batch in _get_line_batches(args.inputfile)
            )
            for future in as_completed(futures):
                for valid, url in future.result():
                    if valid:
                        outputfh.write(url + "\n")
                    # proceed with discarded URLs. to be rewritten
                    elif args.discardedfile is not None:
                        with open(
                            args.discardedfile, "a", encoding="utf-8"
                        ) as discardfh:
                            discardfh.write(url)
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
