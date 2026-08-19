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
    "sphinx_design",
    "sphinxext.opengraph",
    "sphinx_sitemap",
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

# -- HTML output -----------------------------------------------------------

html_theme = "furo"
html_static_path = ["_static"]
html_title = "courlan — URL Filtering and Normalization for Python"

html_theme_options = {
    "source_repository": "https://github.com/adbar/courlan",
    "source_branch": "master",
    "source_directory": "docs/source/",
}
html_baseurl = "https://courlan.readthedocs.io/en/latest/"
sitemap_url_scheme = "{link}"
sitemap_excludes = ["search.html", "genindex.html"]

# -- OpenGraph metadata ----------------------------------------------------

ogp_site_url = "https://courlan.readthedocs.io/en/latest/"
ogp_site_name = "courlan"
ogp_description_length = 200

# -- Intersphinx -----------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
