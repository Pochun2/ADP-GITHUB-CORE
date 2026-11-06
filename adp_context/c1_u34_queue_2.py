import re


def _validate_record(record):
    if not isinstance(record, dict):
        raise ValueError('Record must be a dict')
    if set(record) != {
        'base_sha', 'merge_sha', 'issue_number', 'pr_number', 'ci_names'
    }:
        raise ValueError('Record must contain exactly the required keys')

    for key in ('base_sha', 'merge_sha'):
        value = record[key]
        if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{40}', value) is None:
            raise ValueError('SHA values must be lowercase 40-character hex strings')

    for key in ('issue_number', 'pr_number'):
        value = record[key]
        if type(value) is not int or value <= 0:
            raise ValueError('Issue and PR numbers must be positive integers')

    names = record['ci_names']
    if not isinstance(names, list) or len(names) != 6:
        raise ValueError('ci_names must be a list of exactly six names')
    if any(not isinstance(name, str) for name in names):
        raise ValueError('CI names must be strings')
    if set(names) != {
        'adp-context-suite',
        'adp-context-offline',
        'adp-context-canonical-offline',
        'adp-context-checkpoint-offline',
        'adp-context-github-observation-offline',
        'adp-context-github-publisher-offline',
    }:
        raise ValueError('CI names must contain exactly the required unique names')

    if record['merge_sha'] == record['base_sha']:
        raise ValueError('Merge SHA must differ from base SHA')


def validate_queue_2(previous, current):
    """Validate two consecutive merge records and return their linkage."""
    _validate_record(previous)
    _validate_record(current)

    if current['base_sha'] != previous['merge_sha']:
        raise ValueError('Current base SHA must equal previous merge SHA')
    if current['merge_sha'] in (previous['base_sha'], previous['merge_sha']):
        raise ValueError('Current merge SHA must be new')
    if current['issue_number'] == previous['issue_number']:
        raise ValueError('Issue numbers must differ')
    if current['pr_number'] == previous['pr_number']:
        raise ValueError('PR numbers must differ')

    return {
        'state': 'LINKED',
        'from_sha': previous['merge_sha'],
        'to_sha': current['merge_sha'],
        'issue_pair': [previous['issue_number'], current['issue_number']],
        'pr_pair': [previous['pr_number'], current['pr_number']],
    }
