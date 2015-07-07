URL-tools
=========

Diverse scripts designed to handle URL lists, made available under GPL license.

Designed for Python3, may not work on Python 2.X


Normalize URLs in CommonCrawl reverted prefix format
----------------------------------------------------

Revert URLs to their usual form.

    input: at.anthropology.www/people/whartl/courses_current:http
    output: http://www.anthropology.at/people/whartl/courses_current

Information about usage:

    python3 common-crawl-normalize.py -h

    usage: common-crawl-normalize.py [-h] -i INPUTFILE -o OUTPUTFILE
    optional arguments:
      -h, --help        show this help message and exit
      -i INPUTFILE, --inputfile INPUTFILE
                        name of the input file
      -o OUTPUTFILE, --outputfile OUTPUTFILE
                        name of the output file


Find URLs pointing to WordPress sites
-------------------------------------

Extract URLs which match common WordPress structural patterns for URLs, according to the notion of [permalink structure](https://codex.wordpress.org/Using_Permalinks#Choosing_your_permalink_structure) in the WordPress manual. See [guessing if a URL points to a WordPress blog](http://adrien.barbaresi.eu/blog/guessing-url-points-wordpress-blog.html) for more information.

Information about usage:

     python3 find-wordpress-urls.py -h

    usage: find-wordpress-urls.py [-h] -i INPUTFILE -o OUTPUTFILE [-l]
    optional arguments:
      -h, --help        show this help message and exit
      -i INPUTFILE, --inputfile INPUTFILE
                        name of the input file
      -o OUTPUTFILE, --outputfile OUTPUTFILE
                        name of the output file
      -l, --lax         use lax patterns


Related Projects
----------------

See also [`clean_urls.py`](https://github.com/adbar/flux-toolchain/blob/master/clean_urls.py) component of the [FLUX-toolchain](https://github.com/adbar/flux-toolchain/).
