#!/usr/bin/python
# encoding: utf-8
#
# Copyright (c) 2022 jasantunes@gmail.com
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
#

"""Search Go links."""

from __future__ import print_function, absolute_import

from collections import namedtuple
import functools
import hashlib
from HTMLParser import HTMLParser
from unicodedata import normalize
import os
import re
import sys

from workflow import Workflow3, web, ICON_WARNING

USER_AGENT = 'Alfred-Golinks/{version} ({url})'

UPDATE_SETTINGS = {'github_slug': 'jasantunes/alfred-golinks'}

ICON_UPDATE = 'update-available.png'

# Shown in error logs. Users can find help here
HELP_URL = 'https://github.com/jasantunes/alfred-golinks'

# API endpoint for all golinks sites
API_URL = os.getenv('api_url') or 'https://api.stackexchange.com/2.2/search/advanced'

# Number of results to fetch from API
MAX_RESULTS = int(os.getenv('max_results') or 50)

# How long to cache results for
CACHE_MAX_AGE = int(os.getenv('cache_max_age') or 20)  # seconds

USAGE = """go.py <query>

Search go links.

Usage:
    go.py <query>
    go.py (-h | --help)
    go.py --version

Options:
    -h, --help         show this message and exit
    --version          show version number and exit
"""


# Used to unescape HTML entities
h = HTMLParser()
# Logger populated in if __name__ == '__main__' clause
log = None


# API responses
Answer = namedtuple('Answer', 'shortname link clicks')


def unicodify(s, encoding='utf-8'):
    """Ensure ``s`` is Unicode.

    Returns Unicode unchanged, decodes bytestrings and calls `unicode()`
    on anything else.

    Args:
        s (basestring): String to convert to Unicode.
        encoding (str, optional): Encoding to use to decode bytestrings.

    Returns:
        unicode: Decoded Unicode string.

    """
    if isinstance(s, unicode):
        return s

    if isinstance(s, str):
        return s.decode(encoding, 'replace')

    return unicode(s)


def asciify(s):
    """Ensure string only contains ASCII characters.

    Args:
        s (basestring): Unicode or bytestring.

    Returns:
        unicode: String containing only ASCII characters.

    """
    u = normalize('NFD', unicodify(s))
    s = u.encode('us-ascii', 'ignore')
    return unicodify(s)


def _hash(s):
    """Return hash of string."""
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    h = hashlib.md5(s)
    return h.hexdigest()[:12]


def cache_key(query):
    """Make filesystem-friendly cache key."""
    key = query
    h = _hash(key)
    key = asciify(key)
    key = key.lower()
    key = re.sub(r'[^a-z0-9-_;\.]', '-', key) + '-' + h
    key = 'search/' + re.sub(r'-+', '-', key)
    dirpath = os.path.dirname(wf.cachefile(key))
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)
    log.debug('cache key : %r -> %r', query, key)
    return key


def get_url(url, **params):
    """Retrieve URL using API headers and parameters.

    Args:
        url (str): URL to fetch.
        **params: Query-string parameters.
    """
    # Application ID. Allows up to 10K API hits/day per IP.
    # params.update({'key': 'FgLEU6zgwYULvStDmrgqxg((', 'client_id': '16105'})
    headers = {
        'User-Agent': USER_AGENT.format(version=wf.version, url=wf.help_url)
    }
    r = web.get(url, params, headers=headers)
    log.info(u'[%d] %s', r.status_code, r.url)
    r.raise_for_status()
    return r


def api_call(url, **params):
    """Return response from API."""
    data = get_url(url, **params).json()
    return data


def handle_answer(api_dict):
    """Extract relevant info from API result."""
    return Answer(
        h.unescape(api_dict['shortname']),
        h.unescape(api_dict['url']),
        int(api_dict['clicks'])
    )


def get_answers(query, limit=MAX_RESULTS):
    """Return list of answers from API."""
    params = {
        'short_name': query,
        'limit': limit
    }

    data = api_call(API_URL, **params)
    if not data:
        return {}

    answers = [handle_answer(d) for d in data['sites']]
    answers.sort(key=lambda a: not a.clicks, reverse=False)
    return answers

def do_search(args):
    """Script Filter to search golinks site."""
    # Update available?
    if wf.update_available:
        wf.add_item(u'A newer version is available',
                    u'↩ to install update',
                    autocomplete='workflow:update',
                    icon=ICON_UPDATE)

    query = args['<query>'].strip()

    log.debug(u'query=%r', query)

    # Fetch answers from API
    answers = wf.cached_data(cache_key(query), functools.partial(get_answers, query), max_age=CACHE_MAX_AGE)
    log.info(u'%d answers for query %r', len(answers), query)

    # Show results
    for a in answers:
        wf.add_item(title=a.shortname,
                    subtitle="({clicks}) {link}".format(link=a.link, clicks=a.clicks),
                    arg="http://go/{}".format(a.shortname),
                    uid=a.link,
                    valid=True,
                    icon='icon.png')

    wf.warn_empty(u'No Answers Found', u'Try a different query')
    wf.send_feedback()


def main(wf):
    """Run workflow."""
    from docopt import docopt
    args = docopt(USAGE, wf.args, version=wf.version)
    log.debug('args=%r', args)

    return do_search(args)

if __name__ == '__main__':
    wf = Workflow3(help_url=HELP_URL,
                   update_settings=UPDATE_SETTINGS)
    log = wf.logger
    sys.exit(wf.run(main))
