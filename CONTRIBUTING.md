## How to contribute


If you value this software or depend on it for your product,
consider sponsoring it and contributing to its codebase.
Your support will help ensure the sustainability and growth of the project.

There are many ways to contribute:

  * Sponsor the project: Show your appreciation [on GitHub](https://github.com/sponsors/adbar) or [ko-fi.com](https://ko-fi.com/adbarbaresi).
  * Find bugs and submit bug reports: Help making Courlan an even more robust tool.
  * Write code: Fix bugs or add new features by writing [pull requests](https://docs.github.com/en/pull-requests) with a list of what you have done.


A special thanks to the [contributors](https://github.com/adbar/courlan/graphs/contributors) who have played a part in Courlan.


## Testing and evaluating the code

Courlan requires Python 3.10 or higher. Here is how you can run the tests and code quality checks. Pull requests will only be accepted if the changes are tested and if there are no errors.

1. Install the package along with its development dependencies from a checkout: `pip install -e ".[dev]"`
2. Run the tests and code quality tools:
   - Tests with `pytest`
   - Linting and import sorting with `ruff check courlan tests`
   - Code formatting with `ruff format courlan tests`
   - Type checking with `mypy -p courlan`


For further questions you can use [GitHub issues](https://github.com/adbar/courlan/issues) or [E-Mail](https://adrien.barbaresi.eu/).

Thanks,

Adrien
