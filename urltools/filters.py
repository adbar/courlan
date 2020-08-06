
import re


def typefilter(url):
    # directory
    #if url.endswith('/'):
    #    return False
    # extensions
    if url.endswith(('.atom', '.json', '.css', '.xml', '.js', '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.pdf', '.ogg', '.mp3', '.m4a', '.aac', '.avi', '.mp4', '.mov', '.webm', '.flv', '.ico', '.pls', '.zip', '.tar', '.gz', '.iso', '.swf', '.exe')):
        return False
    # feeds
    if url.endswith(('/feed', '/rss')):
        return False
    # navigation
    if re.search(r'/(?:tags?|schlagwort|category|cat|kategorie|kat|auth?or|page|seite|user|search|gallery|gallerie|labels|archives)/', url) or url.endswith('/index'):
        return False
    # hidden in parameters
    if re.search(r'\.(atom|json|css|xml|js|jpg|jpeg|png|gif|tiff|pdf|ogg|mp3|m4a|aac|avi|mp4|mov|webm|flv|ico|pls|zip|tar|gz|iso|swf)\b', url): # , re.IGNORECASE (?=[&?])
        return False
    # not suitable
    if re.match('https?://banner.', url) or re.match(r'https?://add?s?\.', url):
        return False
    if re.search(r'\b(?:doubleclick|tradedoubler|livestream|live|videos?)\b', url):
        return False
    # default
    return True


def spamfilter(url):
    # TODO: to improve!
    #for exp in (''):
    #    if exp in url:
    #        return False
    if re.search(r'\b(?:adult|amateur|cams?|gangbang|incest|sexyeroti[ck]|sexcam|bild\-?kontakte)\b', url) or re.search(r'\b(?:arsch|fick|porno?)', url) or re.search(r'(?:cash|swinger)\b', url):
    #  or re.search(r'\b(?:sex)\b', url): # live|xxx|sex|ass|orgasm|cams|
        return False
    # default
    return True

