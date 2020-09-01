coURLan: Clean, filter, normalize, and sample URLs
==================================================


.. image:: https://img.shields.io/pypi/v/courlan.svg
    :target: https://pypi.python.org/pypi/courlan
    :alt: Python package

.. image:: https://img.shields.io/pypi/pyversions/courlan.svg
    :target: https://pypi.python.org/pypi/courlan
    :alt: Python versions

.. image:: https://img.shields.io/travis/adbar/courlan.svg
    :target: https://travis-ci.org/adbar/courlan
    :alt: Travis build status

.. image:: https://img.shields.io/codecov/c/github/adbar/courlan.svg
    :target: https://codecov.io/gh/adbar/courlan
    :alt: Code Coverage



Features
--------

Separate `the wheat from the chaff <https://en.wiktionary.org/wiki/separate_the_wheat_from_the_chaff>`_ and optimize crawls by focusing on non-spam HTML pages containing primarily text.

- URL validation and (basic) normalization
- Filters targeting spam and unsuitable content-types
- Sampling by domain name
- Command-line interface (CLI) and Python tool


**Let the coURLan fish out juicy bits for you!**

.. image:: courlan_harns-march.jpg
    :alt: Courlan 
    :align: center
    :width: 65%
    :target: https://commons.wikimedia.org/wiki/File:Limpkin,_harns_marsh_(33723700146).jpg

Here is a `courlan <https://en.wiktionary.org/wiki/courlan>`_ (source: `Limpkin at Harn's Marsh by Russ <https://commons.wikimedia.org/wiki/File:Limpkin,_harns_marsh_(33723700146).jpg>`_, CC BY 2.0).



Installation
------------

This Python package is tested on Linux, macOS and Windows systems, it is compatible with Python 3.4 upwards. It is available on the package repository `PyPI <https://pypi.org/>`_ and can notably be installed with the Python package managers ``pip`` and ``pipenv``:

.. code-block:: bash

    $ pip install courlan # pip3 install on systems where both Python 2 and 3 are installed
    $ pip install --upgrade courlan # to make sure you have the latest version
    $ pip install git+https://github.com/adbar/courlan.git # latest available code (see build status above)



Usage
-----

``courlan`` is designed to work best on English, German and most frequent European languages.

The current logic of detailed/strict URL filtering is on German, for more see ``settings.py``. This can be overriden by `cloning the repository <https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/cloning-a-repository-from-github>`_ and `recompiling the package locally <https://packaging.python.org/tutorials/installing-packages/#installing-from-a-local-src-tree>`_.


Python
~~~~~~

All operations chained:

.. code-block:: python

    >>> from courlan.core import check_url
    # returns url and domain name
    >>> check_url('https://github.com/adbar/courlan')
    ('https://github.com/adbar/courlan', 'github.com')
    # noisy query parameters can be removed
    >>> check_url('https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.org', strict=True)
    ('https://httpbin.org/redirect-to', 'httpbin.org')
    # Check for redirects (HEAD request)
    >>> url, domain_name = check_url(my_url, with_redirects=True)
    # optional argument targeting webpages in German: with_language=False


Helper function, scrub and normalize:

.. code-block:: python

    >>> from courlan.clean import clean_url
    >>> clean_url('HTTPS://WWW.DWDS.DE:80/')
    'https://www.dwds.de'


Basic scrubbing only:

.. code-block:: python

    >>> from courlan.clean import scrub_url


Basic normalization only:

.. code-block:: python

    >>> from urllib.parse import urlparse
    >>> from courlan.clean import normalize_url
    >>> my_url = normalize_url(urlparse(my_url))
    # passing URL strings directly also works
    >>> my_url = normalize_url(my_url)
    # remove unnecessary components and re-order query elements
    >>> normalize_url('http://test.net/foo.html?utm_source=twitter&post=abc&page=2#fragment', strict=True)
    'http://test.net/foo.html?page=2&post=abc'


Basic URL validation only:

.. code-block:: python

    >>> from courlan.filters import validate_url
    >>> validate_url('http://1234')
    (False, None)
    >>> validate_url('http://www.example.org/')
    (True, ParseResult(scheme='http', netloc='www.example.org', path='/', params='', query='', fragment=''))


Sampling by domain name:

.. code-block:: python

    >>> from courlan.core import sample_urls
    >>> my_sample = sample_urls(my_urls, 100)
    # optional: exclude_min=None, exclude_max=None, strict=False, verbose=False



Command-line
~~~~~~~~~~~~

.. code-block:: bash

    $ courlan --inputfile url-list.txt --outputfile cleaned-urls.txt
    $ courlan --help


usage: courlan [-h] -i INPUTFILE -o OUTPUTFILE [-d DISCARDEDFILE] [-v]
               [--strict] [-l] [-r] [--sample] [--samplesize SAMPLESIZE]
               [--exclude-max EXCLUDE_MAX] [--exclude-min EXCLUDE_MIN]

optional arguments:
  -h, --help            show this help message and exit

I/O:
  Manage input and output

  -i INPUTFILE, --inputfile INPUTFILE
                        name of input file (required)
  -o OUTPUTFILE, --outputfile OUTPUTFILE
                        name of output file (required)
  -d DISCARDEDFILE, --discardedfile DISCARDEDFILE
                        name of file to store discarded URLs (optional)
  -v, --verbose         increase output verbosity

Filtering:
  Configure URL filters

  --strict              perform more restrictive tests
  -l, --language        use language filter
  -r, --redirects       check redirects

Sampling:
  Use sampling by host, configure sample size

  --sample              use sampling
  --samplesize SAMPLESIZE
                        size of sample per domain
  --exclude-max EXCLUDE_MAX
                        exclude domains with more than n URLs
  --exclude-min EXCLUDE_MIN
                        exclude domains with less than n URLs



Additional scripts
~~~~~~~~~~~~~~~~~~

Scripts designed to handle URL lists are found under ``helpers``.


License
-------

*coURLan* is distributed under the `GNU General Public License v3.0 <https://github.com/adbar/courlan/blob/master/LICENSE>`_. If you wish to redistribute this library but feel bounded by the license conditions please try interacting `at arms length <https://www.gnu.org/licenses/gpl-faq.html#GPLInProprietarySystem>`_, `multi-licensing <https://en.wikipedia.org/wiki/Multi-licensing>`_ with `compatible licenses <https://en.wikipedia.org/wiki/GNU_General_Public_License#Compatibility_and_multi-licensing>`_, or `contacting me <https://github.com/adbar/courlan#author>`_.

See also `GPL and free software licensing: What's in it for business? <https://www.techrepublic.com/blog/cio-insights/gpl-and-free-software-licensing-whats-in-it-for-business/>`_


Contributing
------------

`Contributions <https://github.com/adbar/courlan/blob/master/CONTRIBUTING.md>`_ are welcome!

Feel free to file issues on the `dedicated page <https://github.com/adbar/courlan/issues>`_.


Author
------

This effort is part of methods to derive information from web documents in order to build `text databases for research <https://www.dwds.de/d/k-web>`_ (chiefly linguistic analysis and natural language processing). A significant challenge resides in the ability to extract and pre-process web texts to meet scientific expectations: Web corpus construction involves numerous design decisions, and this software package can help facilitate collection and enhance corpus quality.

-  Barbaresi, A. "`Generic Web Content Extraction with Open-Source Software <https://konvens.org/proceedings/2019/papers/kaleidoskop/camera_ready_barbaresi.pdf>`_", Proceedings of KONVENS 2019, Kaleidoscope Abstracts, 2019.
-  Barbaresi, A. "`Efficient construction of metadata-enhanced web corpora <https://hal.archives-ouvertes.fr/hal-01371704v2/document>`_", Proceedings of the `10th Web as Corpus Workshop (WAC-X) <https://www.sigwac.org.uk/wiki/WAC-X>`_, 2016.

Contact: see `homepage <https://adrien.barbaresi.eu/>`_ or `GitHub <https://github.com/adbar>`_.
