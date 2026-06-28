import os
import sys

sys.path.insert(0, os.path.abspath("../../"))

from courlan import __author__, __version__

project = "courlan"
author = __author__
release = __version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_typehints = "description"

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = [
    "deflist",
    "colon_fence",
]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = project

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
