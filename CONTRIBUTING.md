## How to contribute


If you value this software or depend on it for your product,
consider sponsoring it and contributing to its codebase.
Your support will help ensure the sustainability and growth of the project.

There are many ways to contribute:

  * Sponsor the project: Show your appreciation [on GitHub](https://github.com/sponsors/adbar) or [ko-fi.com](https://ko-fi.com/adbarbaresi).
  * Find bugs and submit bug reports: Help making Courlan an even more robust tool.
  * Write code: Fix bugs or add new features by writing [pull requests](https://docs.github.com/en/pull-requests) with a list of what you have done.


A special thanks to the [contributors](https://github.com/adbar/courlan/graphs/contributors) who have played a part in Courlan.


## Testing, development setup, and CI expectations

Courlan requires Python 3.10 or higher. Follow these steps to set up a
local development environment, run tests and linters, and prepare a
pull request.

1. Clone and create a virtual environment

```bash
git clone https://github.com/adbar/courlan.git
cd courlan
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies

```bash
pip install --upgrade pip
pip install -e '.[dev]'
```

3. Run tests and quality checks (recommended sequence)

```bash
# run unit tests
pytest -q

# linting
ruff check courlan tests

# apply formatting if needed
ruff format courlan tests

# static typing
mypy -p courlan
```

4. Pre-commit and CI

- Run `pre-commit run --all-files` if pre-commit is configured locally.
- Ensure all CI checks pass (tests, ruff, mypy) before opening a PR. CI
  expectation: tests green, linting passes, and type checks report no
  new errors.

5. Pull request guidance

- Branch from `master` and use a descriptive branch name: `fix/url-cleaning`
  or `feat/urlstore-persistence`.
- Update or add tests for bug fixes and new features.
- Keep commits small and focused. Use conventional commit messages
  where helpful. Include the Co-authored-by trailer when relevant.
- In the PR description, explain the problem, your approach, and any
  user-facing changes (CLI flags, default behavior).

6. Contact and support

If you have questions, open an issue on GitHub or reach out via the
contact details in the README.

Thanks,

Adrien
