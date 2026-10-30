"""
Unit tests for the courlan package: the command-line interface and sampling.
"""

import logging
import os
import signal
import subprocess
import sys
from collections import Counter
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest

from courlan import (
    cli,
    sample_urls,
)

RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")
INPUTFILE = os.path.join(RESOURCES_DIR, "input.txt")


def run_cli(*args, **kwargs):
    "Run the CLI in a subprocess, independent of PATH."
    env = os.environ.copy()
    # Force encoding to utf-8 for Windows (seems to be a problem only in GitHub Actions)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "courlan.cli", *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )


def test_cli(tmp_path, capsys):
    """test the command-line interface"""
    with open(INPUTFILE, encoding="utf-8") as inputfh:
        input_urls = inputfh.read().splitlines()
    outputfile = str(tmp_path / "output.txt")
    discardedfile = str(tmp_path / "discarded.txt")
    testargs = [
        "-i", INPUTFILE,
        "-d", discardedfile,
        "--outputfile", outputfile,
        "-v",
        "--language", "en",
        "--parallel", "2",
    ]  # fmt: skip
    assert cli.parse_args(testargs).parallel == 2
    assert run_cli("--help").returncode == 0

    # _cli_check_urls
    assert cli._cli_check_urls(
        ["123", "https://example.org", "https://a.org/\udce9"]
    ) == [
        (False, "123"),
        (True, "https://example.org"),
        (False, "https://a.org/\udce9"),
    ]

    # end-to-end run
    assert run_cli("-i", INPUTFILE, "-o", outputfile, "-p", "1").returncode == 0
    with open(outputfile, encoding="utf-8") as outputfh:
        assert outputfh.read().splitlines() == input_urls

    # in-process run with processing
    testargs = [
        "-i", INPUTFILE,
        "-d", discardedfile,
        "-o", outputfile,
        "--language", "en",
        "--strict",
        "-p", "1",
    ]  # fmt: skip
    cli.process_args(cli.parse_args(testargs))
    assert not capsys.readouterr().out
    with open(outputfile, encoding="utf-8") as outputfh:
        accepted = outputfh.read().splitlines()
    with open(discardedfile, encoding="utf-8") as discardfh:
        discarded = discardfh.read().splitlines()
    assert "https://www.test.org/en/a-longer-path1.html" in accepted
    assert "https://www.test.org/de/a-longer-path2.html" in discarded
    assert sorted(accepted + discarded) == sorted(input_urls)

    # in-process run with sampling
    samplefile = tmp_path / "sample.txt"
    testargs = ["-i", INPUTFILE, "-o", str(samplefile), "--sample", "10"]
    cli.process_args(cli.parse_args(testargs))
    assert not capsys.readouterr().out
    assert samplefile.read_text(encoding="utf-8").splitlines() == input_urls


def test_cli_main(tmp_path, capsys, restore_courlan_level):
    """test the main() entry point"""
    outputfile = tmp_path / "output.txt"
    testargs = ["", "-i", INPUTFILE, "-o", str(outputfile), "--sample", "1"]
    missing = ["", "-i", str(tmp_path / "missing.txt"), "-o", str(outputfile)]
    with patch.object(sys, "argv", testargs):
        cli.main()
    with patch.object(sys, "argv", missing), pytest.raises(SystemExit) as err:
        cli.main()
    with (
        patch.object(sys, "argv", testargs),
        patch.object(cli, "process_args", side_effect=BrokenPipeError),
        pytest.raises(SystemExit) as pipe_err,
    ):
        cli.main()
    assert pipe_err.value.code == 1
    # one URL per host
    assert len(outputfile.read_text(encoding="utf-8").splitlines()) == 4
    assert err.value.code == 2
    assert capsys.readouterr().err.startswith("courlan: error:")
    # e.g. -p above the Windows limit of ProcessPoolExecutor
    with (
        patch.object(sys, "argv", testargs),
        patch.object(cli, "process_args", side_effect=ValueError("max_workers")),
        pytest.raises(SystemExit) as value_err,
    ):
        cli.main()
    assert value_err.value.code == 2
    assert "courlan: error: max_workers" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform.startswith("win"), reason="no signal dump")
def test_cli_sample_verbose(tmp_path):
    """-v in sampling mode installs the dump of unvisited URLs"""
    testargs = ["-i", INPUTFILE, "-o", str(tmp_path / "s.txt"), "--sample", "1"]
    handler = signal.getsignal(signal.SIGINT)
    cli.process_args(cli.parse_args(testargs))
    assert signal.getsignal(signal.SIGINT) is handler
    cli.process_args(cli.parse_args([*testargs, "-v"]))
    assert signal.getsignal(signal.SIGINT) is not handler


def test_cli_sample_language(tmp_path):
    """-l applies in sampling mode"""
    samplefile = tmp_path / "sample.txt"
    testargs = ["-i", INPUTFILE, "-o", str(samplefile), "--sample", "10", "-l", "de"]
    cli.process_args(cli.parse_args(testargs))
    sample = samplefile.read_text(encoding="utf-8").splitlines()
    assert "https://www.test.org/de/a-longer-path2.html" in sample
    assert "https://www.test.org/en/a-longer-path1.html" not in sample
    assert "https://www.test.org/es/a-longer-path3.html" not in sample


def test_cli_verbose(tmp_path):
    """-v enables debug logging and does not leak warnings without it"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/a\nnot-a-url\n", encoding="utf-8")
    outputfile = str(tmp_path / "output.txt")
    for mode in (["--sample", "10"], ["-p", "1"]):
        quiet = run_cli("-i", str(inputfile), "-o", outputfile, *mode)
        assert quiet.returncode == 0 and not quiet.stderr
        verbose = run_cli("-i", str(inputfile), "-o", outputfile, "-v", *mode)
        assert verbose.returncode == 0 and "DEBUG:courlan" in verbose.stderr

    # -v does not enable debug logging in other libraries
    code = (
        "import logging; from courlan import cli; cli._init_logging(True); "
        "print(logging.getLogger('urllib3').isEnabledFor(logging.DEBUG), "
        "logging.getLogger('courlan.core').isEnabledFor(logging.DEBUG))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.split() == ["False", "True"]


def test_cli_arguments_validation(tmp_path, capsys):
    """invalid arguments end in an argparse error and leave the files untouched"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/a\n", encoding="utf-8")
    infile, outfile = str(inputfile), str(tmp_path / "output.txt")
    hardlink = str(tmp_path / "hardlink.txt")
    os.link(infile, hardlink)
    base = ["-i", infile, "-o", outfile]
    for testargs, message in [
        ([*base, "--sample", "0"], "0 is not an integer of at least 1"),
        ([*base, "-p", "0"], "0 is not an integer"),
        ([*base, "--sample", "x"], "x is not an integer"),
        ([*base, "--exclude-min", "2"], "require --sample"),
        ([*base, "--exclude-max", "2"], "require --sample"),
        ([*base, "--sample", "1", "--exclude-max", "-1"], "at least 0"),
        ([*base, "--sample", "1", "-p", "2"], "--sample"),
        ([*base, "--sample", "1", "-r"], "--sample"),
        ([*base, "--sample", "1", "-d", ""], "--sample"),
        (["-i", infile, "-o", infile], "is the input file"),
        ([*base, "-d", infile], "is the input file"),
        (["-i", infile, "-o", hardlink], "is the input file"),
    ]:
        with pytest.raises(SystemExit) as err:
            cli.parse_args(testargs)
        assert err.value.code == 2
        assert message in capsys.readouterr().err
    assert inputfile.read_text(encoding="utf-8") == "https://example.org/a\n"
    assert not os.path.exists(outfile)
    assert cli.parse_args(["-i", os.devnull, "-o", os.devnull])
    parsed = cli.parse_args([*base, "--sample", "1", "--exclude-max", "0"])
    assert parsed.exclude_max == 0


@pytest.mark.skipif(sys.platform.startswith("win"), reason="symlinks need privileges")
def test_cli_symlink_to_input(tmp_path):
    """an output symlinked to the input is refused"""
    inputfile, symlink = tmp_path / "input.txt", tmp_path / "symlink.txt"
    inputfile.write_text("https://example.org/a\n", encoding="utf-8")
    symlink.symlink_to(inputfile)
    with pytest.raises(SystemExit):
        cli.parse_args(["-i", str(inputfile), "-o", str(symlink)])


def test_cli_file_errors(tmp_path):
    """unusable files end in a clean error"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/a\n", encoding="utf-8")
    infile, outfile = str(inputfile), str(tmp_path / "output.txt")
    (tmp_path / "adir").mkdir()
    for testargs in [
        ["-i", str(tmp_path / "missing.txt"), "-o", outfile],
        ["-i", str(tmp_path / "missing.txt"), "-o", outfile, "--sample", "1"],
        ["-i", str(tmp_path / "adir"), "-o", outfile],
        ["-i", infile, "-o", str(tmp_path / "no" / "out.txt")],
        ["-i", infile, "-o", str(tmp_path / "adir")],
        ["-i", infile, "-o", str(tmp_path / "adir"), "--sample", "1"],
        ["-i", infile, "-o", outfile, "-d", str(tmp_path / "adir")],
    ]:
        result = run_cli(*testargs)
        assert result.returncode == 2
        assert result.stderr.startswith("courlan: error:")
        assert "Traceback" not in result.stderr
    assert inputfile.read_text(encoding="utf-8") == "https://example.org/a\n"


def test_cli_executor_error(tmp_path):
    """a failing executor leaves the outputs untouched"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/a\n", encoding="utf-8")
    outfile, discardfile = tmp_path / "output.txt", tmp_path / "discarded.txt"
    for path in (outfile, discardfile):
        path.write_text("kept\n", encoding="utf-8")
    testargs = ["-i", str(inputfile), "-o", str(outfile), "-d", str(discardfile)]
    with (
        patch.object(cli, "ProcessPoolExecutor", side_effect=ValueError),
        pytest.raises(ValueError),
    ):
        cli.process_args(cli.parse_args(testargs))
    for path in (outfile, discardfile):
        assert path.read_text(encoding="utf-8") == "kept\n"


def test_cli_sample_error(tmp_path):
    """a failure while reading the input leaves the sample output untouched"""
    outfile = tmp_path / "output.txt"
    outfile.write_text("kept\n", encoding="utf-8")
    testargs = ["-i", INPUTFILE, "-o", str(outfile), "--sample", "1"]
    with (
        patch("courlan.cli.UrlStore.add_urls", side_effect=MemoryError),
        pytest.raises(MemoryError),
    ):
        cli.process_args(cli.parse_args(testargs))
    assert outfile.read_text(encoding="utf-8") == "kept\n"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="no /dev/stdout")
def test_cli_broken_pipe(tmp_path):
    """a reader closing the pipe early ends the run quietly"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("".join(f"https://example{i}.org/p\n" for i in range(10**4)))
    for extra in ([], ["--sample", "1"]):
        with subprocess.Popen(
            [sys.executable, "-m", "courlan.cli", "-i", str(inputfile)]
            + ["-o", "/dev/stdout", *extra],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            assert proc.stdout is not None and proc.stderr is not None
            assert proc.stdout.readline().startswith(b"https://")
            proc.stdout.close()
            assert proc.wait() == 1
            assert not proc.stderr.read()


def test_cli_input_opened_once(tmp_path):
    """the input is opened once, so pipes and FIFOs are not consumed twice"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/a\n", encoding="utf-8")
    testargs = ["-i", str(inputfile), "-o", str(tmp_path / "s.txt"), "--sample", "1"]
    with patch("builtins.open", wraps=open) as mock_open:
        cli.process_args(cli.parse_args(testargs))
    assert [c.args[0] for c in mock_open.call_args_list].count(str(inputfile)) == 1


def test_cli_input_handling(tmp_path, caplog):
    """BOM, blank lines and invalid UTF-8 in the input, output in input order"""
    inputfile = tmp_path / "input.txt"
    invalid = [
        b"https://example.org/caf\xe9-cr\xe8me",
        b"https://user:\xe9@example.org/b",
        b"https://ex\xe9.org/a",
    ]
    inputfile.write_bytes(
        b"\xef\xbb\xbfhttps://example.org/first\n\n  \n"
        + b"\r\n".join(invalid)
        + b"\r\nhttps://example.org/last\r\n"
    )
    outputfile = tmp_path / "output.txt"
    discardfile = tmp_path / "discarded.txt"
    testargs = ["-i", str(inputfile), "-o", str(outputfile), "-d", str(discardfile)]
    cli.process_args(cli.parse_args([*testargs, "-p", "1"]))
    assert outputfile.read_text(encoding="utf-8").splitlines() == [
        "https://example.org/first",
        "https://example.org/last",
    ]
    assert discardfile.read_bytes().splitlines() == invalid

    with caplog.at_level(logging.DEBUG, logger="courlan.cli"):
        cli.process_args(cli.parse_args([*testargs[:4], "--sample", "10"]))
    assert "skipped 3 lines with invalid UTF-8" in caplog.text
    assert outputfile.read_text(encoding="utf-8").splitlines() == [
        "https://example.org/first",
        "https://example.org/last",
    ]

    # several batches over several workers keep the input order
    urls = [f"https://example{i % 7}.org/{i}" for i in range(2500)]
    inputfile.write_text("\n".join(urls) + "\n", encoding="utf-8")
    cli.process_args(cli.parse_args([*testargs, "-p", "3"]))
    assert outputfile.read_text(encoding="utf-8").splitlines() == urls


def test_cli_no_discardfile(tmp_path):
    """invalid URLs are dropped silently when no discard file is given"""
    inputfile = tmp_path / "input.txt"
    inputfile.write_text("https://example.org/valid\nnot-a-url\n")
    outputfile = tmp_path / "output.txt"
    testargs = ["-i", str(inputfile), "-o", str(outputfile), "-p", "1"]
    cli._cli_process(cli.parse_args(testargs))
    assert outputfile.read_text().splitlines() == ["https://example.org/valid"]


def test_sample(caplog):
    """test URL sampling"""
    assert not list(sample_urls(["http://test.org/test1", "http://test.org/test2"], 0))
    assert not list(sample_urls(["http://test.org/", "http://test.org"], 10))

    mylist = [
        "http://t.o/t1",
        "http://test.org/test1",
        "http://test.org/test2",
        "http://test2.org/test2",
    ]
    assert len(sample_urls(mylist, 1, verbose=True)) == 2
    assert not sample_urls(mylist, 1, exclude_min=10, verbose=True)
    assert len(sample_urls(mylist, 1, exclude_max=1, verbose=True)) == 1
    bound_urls = [f"http://bound.org/{i}" for i in range(3)]
    assert len(sample_urls(bound_urls, 10, exclude_min=3)) == 3
    assert not sample_urls(bound_urls, 10, exclude_min=4)

    test_urls = [f"https://test.org/{a}" for a in range(1000)]
    example_urls = [f"https://www.example.org/{a}" for a in range(100)]
    other_urls = [f"https://www.other.org/{a}" for a in range(10000)]
    urls = test_urls + example_urls + other_urls
    hosts = Counter(urlsplit(u).hostname for u in sample_urls(urls, 10))
    assert hosts == {"test.org": 10, "www.example.org": 10, "www.other.org": 10}
    hosts = Counter(urlsplit(u).hostname for u in sample_urls(urls, 150))
    assert hosts == {"test.org": 150, "www.example.org": 100, "www.other.org": 150}

    # size exclusions are logged as INFO, or WARNING with verbose
    logger = logging.getLogger("courlan.sampling")
    for verbose, expected in ((False, "INFO"), (True, "WARNING")):
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="courlan.sampling"):
            sample_urls(mylist, 1, exclude_min=10, verbose=verbose)
            assert logger.level == logging.INFO
        records = [r for r in caplog.records if "discarded" in r.message]
        assert records and {r.levelname for r in records} == {expected}
