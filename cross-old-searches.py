#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
================================================================================
  Cross-OLD Searches
================================================================================

Asynchronous cross-linguistic, multi-OLD command-line searching!

This script performs searches across multiple OLDs from the command line and
prints them to stdout.

The OLD (Online Linguistic Database) is software for linguistic fieldwork. The
OLD is used to build RESTful web services that allow you to build and query
databases of linguistic fieldwork data over the Internet. See
http://www.onlinelinguisticdatabase.org.


Usage
================================================================================

.::

    $ python cross-old-searches.py

The script will prompt you for your username and password. Note that you must
have the same username and password for all of the OLDs you are searching over,
which is a good idea anyways.

Change `OLDS` and `LANGUAGES` below to match the OLDs that you have access to.


Example Search
================================================================================

This search will return all grammatical forms that contain the word "quickly"
in one of their translation values.::

    ['and',
        [
            ['Form', 'grammaticality', '=', ''],
            ['Form', 'translations', 'transcription', 'regex', '(^| )([qQ]uickly)($| )']
        ]
    ]


Dependencies
================================================================================

Python Twisted must be installed.


"""

import requests
import getpass
import sys
import pprint
import json
import itertools
import unicodedata
import re
from twisted.internet import reactor, threads


USERNAME = ''
PASSWORD = ''

# Change the following tuple and dict to match the OLDs that you have access to.
OLDS = ('bla',
        'cac',
        'kab',
        'batumi_kartuli',
        'khm',
        'kut',
        'rkm',
        'mor',
        'nep',
        'oka',
        'gla')

LANGUAGES = {
    'bla': 'Blackfoot',
    'cac': 'Chuj',
    'kab': 'Kabyle',
    'batumi_kartuli': 'Batumi Kartuli',
    'khm': 'Khmer',
    'kut': 'Ktunaxa',
    'rkm': 'Marka',
    'mor': 'Moro',
    'nep': 'Nepali',
    'oka': 'Okanagan',
    'gla': 'Scottish Gaelic'
}

# ANSI escape sequences for formatting command-line output.
ANSI_HEADER = '\033[95m'
ANSI_OKBLUE = '\033[94m'
ANSI_OKGREEN = '\033[92m'
ANSI_WARNING = '\033[93m'
ANSI_FAIL = '\033[91m'
ANSI_ENDC = '\033[0m'
ANSI_BOLD = '\033[1m'
ANSI_UNDERLINE = '\033[4m'


def prompt_for_search():
    """Prompt the user to enter a new search.

    """

    sentinel = '' # ends when this string is seen
    search = []
    print '\nEnter an OLD search expression (or Enter to exit): ',
    for line in iter(raw_input, sentinel):
        search.append(line)
    search = '\n'.join(search)
    if search.strip() == '':
        return False
    try:
        search = eval(search)
        assert type(search) is list
        return search
    except Exception, e:
        return None


class AsyncSession(requests.Session):
    """Create Requests sessions using this class and requests will return
    Twisted deferred objects.

    """

    def request(self, *args, **kwargs):
        func = super(AsyncSession, self).request
        return threads.deferToThread(func, *args, **kwargs)


class OLDSearcher:
    """Asynchronous cross-linguistic, multi-OLD command-line searching.

    """

    def __init__(self, olds):
        self.olds = olds
        self.searches = []
        self.logins = 0
        self.next = self.next_search
        print 'Logging in to %d OLDs ...' % len(OLDS),
        sys.stdout.flush()
        self.sessions = dict([(oldurl, self.get_session(oldurl)) for oldurl in
            OLDS])

    def next_search(self):
        if self.searches:
            self.search(self.searches.pop())
        else:
            new_search = prompt_for_search()
            if new_search:
                self.searches.append(new_search)
                self.next_search()
            else:
                if new_search is False:
                    print 'Goodbye.'
                else:
                    print 'Sorry, that\'s not a valid search expression.'
                reactor.stop()

    def add_search(self, search):
        self.searches.append(search)

    def get_simplex_filters(self, searchexpr):
        sf = []
        if len(searchexpr) in [4, 5]:
            sf.append(searchexpr)
        elif searchexpr[0] == 'not':
            return []
        else:
            for new_searchexpr in searchexpr[1]:
                sf += self.get_simplex_filters(new_searchexpr)
        return sf

    def get_search_highlighter(self):
        """TODO: add search highlighters so that users can quickly see

        """

        sh = {}
        simplex_filters = self.get_simplex_filters(self.searchexpr)
        for filter in simplex_filters:
            if len(filter) == 4:
                attr = filter[1]
                rel = filter[2]
                patt = filter[3]
            elif len(filter) == 5:
                attr = filter[1]
                rel = filter[3]
                patt = filter[4]
            if rel == 'regex':
                p = re.compile('(' + patt + ')')
                sh.setdefault(attr, []).append(lambda x: p.sub('\033[92m\\1\033[0m', x))
        new_sh = {}
        for attr, funclist in sh.items():
            if len(funclist) > 1:
                def newfunc(x):
                    for func in funclist:
                        x = func(x)
                    return x
                new_sh[attr] = newfunc
            else:
                new_sh[attr] = funclist[0]
        return new_sh


    def search(self, search):
        print 'Searching across %d OLDs. Please wait...' % len(OLDS),
        sys.stdout.flush()
        self.searchexpr = search
        self.search_highlighter = self.get_search_highlighter()
        self.search_counts = {}
        self.search_results = {}
        self.next = self.request_all_search_results
        self.request_search_counts()

    def request_search_counts(self):
        for old in self.olds:
            self.request_search_count(old)

    def print_search_results(self):
        for old, search_results in self.search_results.iteritems():
            if len(search_results):
                print '\n\n'
                print ANSI_HEADER
                print '%s OLD %d' % (LANGUAGES[old], len(search_results))
                print '=' * 80
                print ANSI_ENDC
                print
                for index, form in enumerate(search_results):
                    self.print_form(index + 1, form)

        print '\n\n'
        print '%s%s' % (ANSI_HEADER, '=' * 80)
        print '  Summary'
        print '=' * 80
        print ANSI_ENDC
        print 'Search'
        print '-' * 80
        print
        pprint.pprint(self.searchexpr)
        print
        print 'Counts by Language'
        print '-' * 80
        print
        for old, search_results in self.search_results.iteritems():
            if len(search_results):
                print '%s: %d' % (LANGUAGES[old], len(search_results))
        print
        print '=' * 80
        self.next_search()

    def request_all_search_results(self):
        self.next = self.print_search_results
        new_search_counts = {}
        for old, count in self.search_counts.items():
            if count != 0:
                new_search_counts[old] = count
        self.search_counts = new_search_counts
        for old in self.olds:
            self.get_search_results(old)

    def get_url(self, old):
        return 'https://projects.linguistics.ubc.ca/%sold/' % old

    def get_session(self, old):
        s = AsyncSession()
        url = self.get_url(old)
        s.headers.update({'Content-Type': 'application/json'})
        defer = s.post('%slogin/authenticate' % url,
            data=json.dumps({
                'username': USERNAME,
                'password': PASSWORD}))
        defer.addCallback(self.verify_logged_in)
        return s

    def verify_logged_in(self, resp):
        try:
            assert resp.json().get('authenticated') == True
            self.logins += 1
            if self.logins == len(self.olds):
                print 'Done.'
                self.next()
        except Exception, e:
            print 'Failed.'
            reactor.stop()

    def get_payload(self, search):
        return json.dumps({
            "query": {
                "filter": search,
            }
        })

    def get_payload_one(self, search):
        return json.dumps({
            "query": {
                "filter": search,
            },
            "paginator": {
                "page": 1,
                "items_per_page": 1
            }
        })

    def request_search_count(self, old):
        s = self.sessions[old]
        defer = s.post('%sforms/search' % self.get_url(old),
            data=self.get_payload_one(self.searchexpr))
        defer.addCallback(self.get_search_count_adder(old))

    def get_search_count_adder(self, old):
        def search_count_adder(resp):
            resp = resp.json()
            try:
                assert resp.get('paginator')
                assert type(resp['paginator'].get('count')) is int
            except Exception, e:
                print 'Sorry, that\'s not a valid OLD search expression.'
                reactor.stop()
                # print 'ERROR'
                # print e
                # print resp
            self.search_counts[old] = resp['paginator']['count']
            if len(self.search_counts) == len(self.olds):
                self.next()
        return search_count_adder

    def get_search_results(self, old):
        s = self.sessions[old]
        defer = s.post('%sforms/search' % self.get_url(old),
            data=self.get_payload(self.searchexpr))
        defer.addCallback(self.get_search_results_adder(old))

    def get_search_results_adder(self, old):
        def search_results_adder(resp):
            self.search_results[old] = resp.json()
            if len(self.search_results) == len(self.olds):
                self.next()
        return search_results_adder

    def get_true_width(self, string):
        # return len([c for c in string if unicodedata.combining(c) == 0])
        # return len(unicodedata.normalize('NFC', string))
        return len(string)

    def get_word_widths(self, string):
        return [self.get_true_width(word) for word in string.split(' ')]

    def get_col_widths(self, values_array):
        lengths = [self.get_word_widths(value) for value in values_array]
        return [max(x) or 0 for x in itertools.izip_longest(*lengths)]

    def pad_content(self, content, colwidths):
        words = []
        for index, word in enumerate(content.split(' ')):
            width = colwidths[index]
            while len(word) < width:
                word = word + u' '
            words.append(word)
        return u'  '.join(words)

    def print_igt_fields(self, index, form):
        contents = {}
        fields = (
            'narrow_phonetic_transcription',
            'phonetic_transcription',
            'transcription',
            'morpheme_break',
            'morpheme_gloss',
            'syntactic_category_string'
        )
        for f in fields:
            if form[f]:
                contents[f] = form[f]
        colwidths = self.get_col_widths(contents.values())
        first = True
        for field in fields:
            if field in contents:
                content = contents[field]
                sh = self.search_highlighter.get(field, lambda x: x)
                if first:
                    first = False
                    print index,
                else:
                    print '      ',
                print sh(self.pad_content(content, colwidths))

    def print_translations(self, form):
        if form['translations']:
            sh = self.search_highlighter.get('translations', lambda x: x)
            for t in form['translations']:
                tr = '       `%s%s`' % (t['grammaticality'], sh(t['transcription']))
                print tr

    def print_form(self, index, form):
        index = '%d)' % index
        while len(index) < 6:
            index = index + ' '
        self.print_igt_fields(index, form)
        self.print_translations(form)
        print


def banner():
    print ANSI_HEADER
    print '=' * 80
    print '  Cross-OLD Search'
    print '=' * 80
    print
    print ANSI_ENDC


def main():
    banner()
    global USERNAME
    global PASSWORD
    USERNAME = raw_input('Username: ')
    PASSWORD = getpass.getpass('Password: ')
    os = OLDSearcher(OLDS)
    reactor.run()


################################################################################
# Some example searches
################################################################################

# Looks for "quick(ly)" or "fast" in glosses or translations.
search1 = ['and',
    [
        ['Form', 'grammaticality', '=', ''],
        ['or',
            [
                ['Form', 'morpheme_gloss', 'regex', '(^| |-|=)([qQ]uick(ly)?|fast)($| |-|=)'],
                ['Form', 'translations', 'transcription', 'regex', '(^| |-|=)([qQ]uick(ly)?|fast)($| |-|=)']
            ]
        ]
    ]
]

# Looks for "big" in morpheme gloss.
search2 = ['and',
    [
        ['Form', 'grammaticality', '=', ''],
        ['Form', 'morpheme_gloss', 'regex', '(^| |-|=)[Bb]ig($| |-|=)']
    ]
]

# Looks for "quickly" in translations.
search3 = ['and',
    [
        ['Form', 'grammaticality', '=', ''],
        ['Form', 'translations', 'transcription', 'regex', '(^| )([qQ]uickly)($| )']
    ]
]

if __name__ == '__main__':
    main()

