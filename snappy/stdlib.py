
_report = {'result': None}
_globals = {}


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


# Builtin Report methods

def reportTrue():
    return doReport(True)


def reportFalse():
    return doReport(False)


def reportNot(a):
    return doReport(not a)


def reportEquals(a, b):
    if isinstance(a, basestring) and isinstance(b, basestring):
        return doReport(a.lower() == b.lower())
    return doReport(a == b)


def reportAnd(a, b):
    return doReport(a and b)


def reportOr(a, b):
    return doReport(a or b)


def reportGreaterThan(a, b):
    return doReport(a > b)


def reportLessThan(a, b):
    return doReport(a < b)


def reportNewList(a):
    # a list is expected as the first argument
    return doReport(a)


def reportCAR(a):
    return doReport(a[0])


def reportCDR(a):
    return doReport(a[1:])


def reportCONS(a, b):
    return doReport([a] + b)


def reportJoinWords(a):
    return doReport("".join(a))


def reportLetter(a, b):
    if len(b) >= a:
        return doReport(b[a - 1])
    return ''


def reportListItem(a, b):
    return doReport(b[a - 1])


def reportStringSize(a):
    return doReport(len(a))
