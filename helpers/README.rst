Helpers
=======


Normalize URLs in CommonCrawl reverted prefix format
----------------------------------------------------

Revert URLs to their usual form:

- Input: ``at.anthropology.www/people/whartl/courses_current:http``
- Output: ``http://www.anthropology.at/people/whartl/courses_current``

The script also tries to normalize the URLs and to catch potential errors during the process. It works better if the URLs are sorted.

Information about usage: ``python3 common-crawl-normalize.py -h``


Find URLs pointing to WordPress sites
-------------------------------------

Extract URLs which match common WordPress structural patterns for URLs, according to the notion of `permalink structure <https://codex.wordpress.org/Using_Permalinks#Choosing_your_permalink_structure>`_ in the WordPress manual. See `guessing if a URL points to a WordPress blog <http://adrien.barbaresi.eu/blog/guessing-url-points-wordpress-blog.html>`_ for more information.

Information about usage: ``python3 find-wordpress-urls.py -h``