
_report = {'result': None}
_globals = {}


def equals(a, b):
    if isinstance(a, basestring) and isinstance(b, basestring):
        return a.lower() == b.lower()
    return a == b


def cleanReport():
    global _report
    global _globals
    _report = {'result': None}
    _globals = {}


def doReport(result, name=None):
    _report['result'] = result
    return result


def dumpReport(script_file):
    import json
    import os
    result_file = os.path.join(os.path.dirname(script_file), 'result.json')
    result = open(result_file, 'w')
    result.write(json.dumps(_report['result']))
