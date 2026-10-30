"""
Implements a basic command-line interface.
"""

import argparse
import logging
import os
import stat
import sys
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from functools import partial
from itertools import islice
from typing import IO

from .core import check_url
from .sampling import _make_sample
from .urlstore import UrlStore

LOGGER = logging.getLogger(__name__)


def _int_at_least(value: str, minimum: int) -> int:
    "Argparse type for integers with a lower bound."
    message = f"{value} is not an integer of at least {minimum}"
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(message) from None
    if number < minimum:
        raise argparse.ArgumentTypeError(message)
    return number


def _same_path(first: str, second: str) -> bool:
    "Tell if two paths point to the same regular file."
    return (
        os.path.isfile(first)
        and os.path.isfile(second)
        and os.path.samefile(first, second)
    )


class _CliError(ValueError):
    "Unusable arguments found once processing has started."


def parse_args(args: Sequence[str] | None) -> argparse.Namespace:
    """Define parser for command-line arguments"""
    argsparser = argparse.ArgumentParser(
        description="Command-line interface for Courlan"
    )
    group1 = argsparser.add_argument_group("I/O", "Manage input and output")
    group1.add_argument(
        "-i",
        "--inputfile",
        help="name of input file (required)",
        required=True,
    )
    group1.add_argument(
        "-o",
        "--outputfile",
        help="name of output file (required)",
        required=True,
    )
    group1.add_argument(
        "-d",
        "--discardedfile",
        help="name of file to store discarded URLs (optional)",
    )
    group1.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    group1.add_argument(
        "-p",
        "--parallel",
        help="number of parallel processes (batch mode only)",
        type=partial(_int_at_least, minimum=1),
    )
    group2 = argsparser.add_argument_group("Filtering", "Configure URL filters")
    group2.add_argument(
        "--strict", help="perform more restrictive tests", action="store_true"
    )
    group2.add_argument("-l", "--language", help="use language filter (ISO 639-1 code)")
    group2.add_argument(
        "-r", "--redirects", help="check redirects", action="store_true"
    )
    group3 = argsparser.add_argument_group(
        "Sampling", "Use sampling by host, configure sample size"
    )
    group3.add_argument(
        "--sample",
        help="size of sample per domain",
        type=partial(_int_at_least, minimum=1),
    )
    group3.add_argument(
        "--exclude-max",
        help="exclude domains with more than n URLs",
        type=partial(_int_at_least, minimum=0),
    )
    group3.add_argument(
        "--exclude-min",
        help="exclude domains with less than n URLs",
        type=partial(_int_at_least, minimum=0),
    )
    parsed = argsparser.parse_args(args)
    if parsed.sample is None and (
        parsed.exclude_max is not None or parsed.exclude_min is not None
    ):
        argsparser.error("--exclude-max and --exclude-min require --sample")
    if parsed.sample is not None and (
        parsed.parallel is not None
        or parsed.redirects
        or parsed.discardedfile is not None
    ):
        argsparser.error("-p, -r and -d cannot be used with --sample")
    for path in (parsed.outputfile, parsed.discardedfile):
        if path is not None and _same_path(parsed.inputfile, path):
            argsparser.error(f"output file is the input file: {path}")
    return parsed


def _cli_check_urls(
    urls: list[str],
    strict: bool = False,
    with_redirects: bool = False,
    language: str | None = None,
) -> list[tuple[bool, str]]:
    "Internal function to be used with CLI multiprocessing."
    results = []
    for url in urls:
        if not _is_utf8(url):
            results.append((False, url))
            continue
        result = check_url(
            url,
            strict=strict,
            with_redirects=with_redirects,
            language=language,
        )
        if result is not None:
            results.append((True, result[0]))
        else:
            results.append((False, url))
    return results


def _open(path: str, mode: str = "r") -> IO[str]:
    "Open a CLI file, keeping invalid UTF-8 bytes as surrogates."
    encoding = "utf-8-sig" if mode == "r" else "utf-8"
    return open(path, mode, encoding=encoding, errors="surrogateescape")


def _is_utf8(line: str) -> bool:
    "Tell if a line read with surrogateescape had only valid UTF-8."
    try:
        line.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _batch_lines(inputfh: Iterable[str], size: int) -> Iterator[list[str]]:
    "Read the non-empty input lines in batches."
    lines = filter(None, map(str.strip, inputfh))
    while batch := list(islice(lines, size)):
        yield batch


def _init_logging(verbose: bool) -> None:
    "Configure logging in the main process and in the workers."
    logging.basicConfig(level=logging.ERROR)
    logging.getLogger("courlan").setLevel(logging.DEBUG if verbose else logging.ERROR)


def _cli_sample(args: argparse.Namespace) -> None:
    "Sample URLs on the CLI."
    urlstore = UrlStore(
        compressed=True,
        language=args.language,
        strict=args.strict,
        verbose=args.verbose,
    )
    with _open(args.inputfile) as inputfh:
        for batch in _batch_lines(inputfh, 10**5):
            urls = list(filter(_is_utf8, batch))
            if len(urls) < len(batch):
                LOGGER.debug(
                    "skipped %s lines with invalid UTF-8", len(batch) - len(urls)
                )
            urlstore.add_urls(urls)
    # output last, so a read failure does not truncate it
    with _open(args.outputfile, "w") as outputfh:
        for url in _make_sample(
            urlstore,
            args.sample,
            exclude_min=args.exclude_min,
            exclude_max=args.exclude_max,
            verbose=args.verbose,
        ):
            outputfh.write(url + "\n")


def _cli_process(args: argparse.Namespace) -> None:
    "Read input file bit by bit and process URLs in batches."
    with ExitStack() as stack:
        # input and executor first, so bad arguments do not truncate the outputs.
        # Workers only start on submit, so a failure there still truncates them.
        inputfh = stack.enter_context(_open(args.inputfile))
        try:
            executor = ProcessPoolExecutor(
                max_workers=args.parallel,
                initializer=_init_logging,
                initargs=(args.verbose,),
            )
        except ValueError as err:
            # e.g. -p above the Windows limit
            raise _CliError(err) from err
        # on errors, drop the queued batches, running ones still finish
        stack.callback(executor.shutdown, cancel_futures=True)
        # open every output before truncating any, and compare the opened files
        outputfh = stack.enter_context(_open(args.outputfile, "a"))
        discardfh = (
            stack.enter_context(_open(args.discardedfile, "a"))
            if args.discardedfile is not None
            else None
        )
        handles = [fh for fh in (outputfh, discardfh) if fh is not None]
        stats = [os.fstat(fh.fileno()) for fh in handles]
        regular = [stat.S_ISREG(fstat.st_mode) for fstat in stats]
        if len(stats) == 2 and regular[0] and os.path.samestat(*stats):
            raise _CliError(f"output file is the discarded file: {args.outputfile}")
        # pipes and devices cannot be truncated
        for fh, is_regular in zip(handles, regular, strict=True):
            if is_regular:
                fh.truncate(0)
        batches = _batch_lines(inputfh, 1000)
        # submit up to 1000 batches at a time and write results in input order
        while chunk := list(islice(batches, 1000)):
            futures = [
                executor.submit(
                    _cli_check_urls,
                    batch,
                    strict=args.strict,
                    with_redirects=args.redirects,
                    language=args.language,
                )
                for batch in chunk
            ]
            for future in futures:
                for valid, url in future.result():
                    if valid:
                        outputfh.write(url + "\n")
                    elif discardfh is not None:
                        discardfh.write(url + "\n")


def process_args(args: argparse.Namespace) -> None:
    """Start processing according to the arguments"""
    if args.sample is not None:
        _cli_sample(args)
    else:
        _cli_process(args)


def main() -> None:
    """Run as a command-line utility."""
    args = parse_args(sys.argv[1:])
    _init_logging(args.verbose)
    try:
        process_args(args)
    except BrokenPipeError:
        # the reader stopped early, e.g. with head, 128 + SIGPIPE as in shells
        sys.exit(141)
    except (OSError, _CliError) as err:
        print(f"courlan: error: {err}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
