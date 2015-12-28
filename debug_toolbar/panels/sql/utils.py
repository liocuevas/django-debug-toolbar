from __future__ import absolute_import, unicode_literals

import re

import sqlparse
from django.utils.html import escape
from django.conf import settings
from django.apps import apps
from sqlparse import tokens as T


class BoldKeywordFilter:
    """sqlparse filter to bold SQL keywords"""
    def process(self, stack, stream):
        """Process the token stream"""
        for token_type, value in stream:
            is_keyword = token_type in T.Keyword
            if is_keyword:
                yield T.Text, '<strong>'
            yield token_type, escape(value)
            if is_keyword:
                yield T.Text, '</strong>'


def reformat_sql(sql):
    stack = sqlparse.engine.FilterStack()
    stack.preprocess.append(BoldKeywordFilter())  # add our custom filter
    stack.postprocess.append(sqlparse.filters.SerializerUnicode())  # tokens -> strings
    return swap_fields(''.join(stack.run(sql)))


def swap_fields(sql):
    expr = r'SELECT</strong> (...........*?) <strong>FROM'
    subs = (r'SELECT</strong> '
            r'<a class="djDebugUncollapsed djDebugToggle" href="#">&#8226;&#8226;&#8226;</a> '
            r'<a class="djDebugCollapsed djDebugToggle" href="#">\1</a> '
            r'<strong>FROM')
    return re.sub(expr, subs, sql)


def contrasting_color_generator():
    """
    Generate constrasting colors by varying most significant bit of RGB first,
    and then vary subsequent bits systematically.
    """
    def rgb_to_hex(rgb):
        return '#%02x%02x%02x' % tuple(rgb)

    triples = [(1, 0, 0), (0, 1, 0), (0, 0, 1),
               (1, 1, 0), (0, 1, 1), (1, 0, 1), (1, 1, 1)]
    n = 1 << 7
    so_far = [[0, 0, 0]]
    while True:
        if n == 0:  # This happens after 2**24 colours; presumably, never
            yield "#000000"  # black
        copy_so_far = list(so_far)
        for triple in triples:
            for previous in copy_so_far:
                rgb = [n * triple[i] + previous[i] for i in range(3)]
                so_far.append(rgb)
                yield rgb_to_hex(rgb)
        n >>= 1


def cleanse_result(headers, result):
    """
    Remove sensitive information from queries results
    """
    BASE_PATTERN = 'password|email|username|is_staff|is_superuser'
    CLEANSED_SUBSTITUTE = '********************'
    column_blacklist = getattr(settings, 'DEBUG_TOOLBAR_SQL_COLUMN_BLACKLIST', None)

    if column_blacklist is not None:
        for c in column_blacklist:
            BASE_PATTERN += '|' + c
    hidden_fields = re.compile(BASE_PATTERN)
    for i, e in enumerate(headers):
        if hidden_fields.search(e):
            result = list(result)
            for index, row in enumerate(result):
                row = list(row)
                row[i] = CLEANSED_SUBSTITUTE
                result[index] = row
    return result


def check_blacklist(raw_sql):
    """
    Check if the table is in blacklist
    """
    TABLE_BLACKLIST = getattr(settings, 'DEBUG_TOOLBAR_SQL_TABLE_BLACKLIST', None)
    if TABLE_BLACKLIST is None:
        return False
    for app, models in TABLE_BLACKLIST.iteritems():
        for m in models:
            table_name = apps.get_model(app, m)._meta.db_table
            if table_name in raw_sql:
                return True
    return False
