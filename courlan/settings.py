"""
General settings for package execution.
"""

## This file is available from https://github.com/adbar/courlan
## under GNU GPL v3 license


# http://www.alexa.com/topsites/countries/DE
BLACKLIST = ('akamai', 'amzn', 'amazon', 'baidu', 'bit', 'bongacams', 'cloudfront', 'delicious', 'digg', 'ebay', 'ebay-kleinanzeigen', 'facebook', 'feedburner', 'flickr', 'gettyimages', 'gmx', 'google', 'gravatar', 'http', 'imgur', 'immobilienscout24', 'instagr', 'instagram', 'last', 'linkedin', 'live', 'livejasmin', 'localhost', 'mail', 'netflix', 'ok', 'otto', 'paypal', 'pinterest', 'pornhub', 'postbank', 'qq', 'reddit', 'sina', 'sohu', 'soundcloud', 'taobao', 'telegram', 'tmall', 'twitch', 'twitter', 'twitpic', 'txxx', 'vk', 'vkontakte', 'vimeo', 'web', 'weibo', 'whatsapp', 'xhamster', 'xvideos', 'yahoo', 'yandex', 'youtube', 'youtu')
# ...

ALLOWED_PARAMS = ('aid', 'article_id', 'artnr', 'id', 'itemid', 'objectid', 'p', 'page', 'pagenum', 'page_id', 'pid', 'post', 'postid', 'product_id')
CONTROL_PARAMS = ('lang', 'language')
TARGET_LANG_DE = ('de', 'deutsch', 'ger', 'german')
TARGET_LANG_EN = ('en', 'english', 'eng') # 'en_US', ''
# accepted_lang = ('en')
