"""
URL filter and manipulation tools
http://github.com/adbar/courlan
"""

# workaround for open() with encoding=''
from codecs import open

from os import path
from setuptools import setup


here = path.abspath(path.dirname(__file__))


def readme():
    with open(path.join(here, 'README.rst'), 'r', 'utf-8') as readmefile:
        return readmefile.read()


setup(
    name='courlan',
    version='0.2.1',
    description='Clean, filter, normalize, and sample URLs',
    long_description=readme(),
    classifiers=[
        # As from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 3 - Alpha',
        #'Development Status :: 4 - Beta',
        #'Development Status :: 5 - Production/Stable',
        #'Development Status :: 6 - Mature',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Text Processing :: Filters',
    ],
    keywords=['urls', 'url-parsing', 'url-manipulation', 'preprocessing', 'validation', 'webcrawling'],
    url='http://github.com/adbar/courlan',
    author='Adrien Barbaresi',
    author_email='barbaresi@bbaw.de',
    license='GPLv3+',
    packages=['courlan'],
    #package_data={},
    include_package_data=True,
    python_requires='>=3.4',
    install_requires=[
        'tldextract',
    ],
    #extras_require=extras,
    entry_points = {
        'console_scripts': ['courlan=courlan.cli:main'],
    },
    # platforms='any',
    tests_require=['pytest', 'tox'],
    zip_safe=False,
)
