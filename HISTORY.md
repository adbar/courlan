## History / Changelog


### 0.4.1

- keep trailing slashes to avoid redirection
- fixes: normalization and crawlable URLs


### 0.4.0

- URL manipulation tools added: extract parts, fix relative URLs
- filters added: language, navigation and crawls
- more robust link handling and extraction
- removed support for Python 3.4


### 0.3.1

- improve filter precision


### 0.3.0

- reduced dependencies: replace requests with bare urllib3, and tldextract with tld for Python 3.6 upwards
- better path and fragment normalization


### 0.2.3

- Python 3.9 compatibility
- Simplified imports
- Bug fixes


### 0.2.2

- English and German language filters
- Function to detect external links
- Support for domain blacklisting 


### 0.2.1

- Less aggressive strict filters
- CLI bug fixed


### 0.2.0

- Cleaner and more efficient filtering
- Helper functions to scrub, clean and normalize
- Removed two dependencies with more extensive usage of urllib.parse


### 0.1.0

- Cleaning and filtering targeting non-spam HTML pages with primarily text
- URL validation
- Sampling by domain name
- Command-line interface (CLI) and Python tool
