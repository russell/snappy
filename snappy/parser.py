import ast
import codegen

import lxml.etree
import lxml.sax
import logging
from xml.sax.handler import ContentHandler

LOG = logging.getLogger(__name__)


class Block(object):
    _entered_block = False

    def __init__(self, parser):
        self.parser = parser
        self.text = ''

    def pushParser(self, parser):
        """Push a block parser onto the parser stack."""
        return self.parser.pushParser(parser)

    def popParser(self):
        """Pop a block parser from the parser stack."""
        return self.parser.popParser()

    def enter_block(self, name, qname, attributes):
        # Handle expressions
        fn = (attributes.getValueByQName('s')
              if attributes.has_key((None, 's')) else '')
        if fn == self.__class__.__name__:
            self._entered_block = True
            return
        if fn in builtin_parsers:
            block_parser = builtin_parsers[fn](self)
            return self.pushParser(block_parser)

        # Handle variables
        var = (attributes.getValueByQName('var')
              if attributes.has_key((None, 'var')) else '')
        if var:
            block_parser = namedBlock(self, var)
            return self.pushParser(block_parser)

    def leave_block(self):
        return self.popParser()

    def characters(self, data):
        self.text = data

    def __str__(self):
        return str(codegen.to_source(self.to_ast()))


class namedBlock(Block):

    def __init__(self, parser, name):
        super(namedBlock, self).__init__(parser)
        self.name = name

    def to_ast(self):
        return ast.Name(self.name, ast.Load())


class literalBlock(Block):

    def __init__(self, value):
        self.value = value

    def to_ast(self):
        try:
            value = ast.Num(int(self.value))
        except:
            value = ast.Str(self.value)
        return value


class passBlock(Block):
    def to_ast(self):
        return ast.Expr([ast.Name('Pass', ast.Load())])


class reportTrue(Block):
    def to_ast(self):
        # NOTE needs to be wrapped it a ast.Expr([]) in some cases.
        return ast.Name('True', ast.Load())


class reportNewList(Block):
    def __init__(self, parser):
        super(reportNewList, self).__init__(parser)
        self.values = []

    def leave_l(self):
        self.values.append(literalBlock(self.text))

    def to_ast(self):
        return ast.List([v.to_ast() for v in self.values], ast.Load())


class doSetVar(Block):
    def __init__(self, parser):
        super(doSetVar, self).__init__(parser)
        self.variable = None
        self.value = None

    def leave_l(self):
        if not self.variable:
            self.variable = self.text
        elif not self.value:
            self.value = literalBlock(self.text)

    def enter_block(self, name, qname, attributes):
        block = super(doSetVar, self).enter_block(name, qname, attributes)
        if not block:
            return
        self.value = block

    def to_ast(self):
        name = [ast.Name(self.variable, ast.Load())]
        return ast.Assign(name, self.value.to_ast())


class doDeclareVariables(Block):

    def __init__(self, parser):
        super(doDeclareVariables, self).__init__(parser)
        self.variables = []

    def leave_l(self):
        self.variables.append(self.text)

    def to_ast(self):
        names = ast.Tuple([ast.Name(var, ast.Load())
                          for var in self.variables],
                          ast.Load())
        values = ast.Tuple([ast.Name('None', ast.Load())
                            for var in self.variables],
                           ast.Load())
        assign = ast.Assign([names], values)
        return assign


class doIf(Block):
    current_part = None

    def __init__(self, parser):
        super(doIf, self).__init__(parser)
        self.test = None
        self.expr1 = []

    def next_part(self):
        if self.current_part:
            return self.current_part
        if not self.test:
            return 'test'
        elif not self.expr1:
            return 'expr1'
        print self.__dict__
        print self.test.__dict__
        raise Exception("Lost position in if statement")

    def enter_block(self, name, qname, attributes):
        block = super(doIf, self).enter_block(name, qname, attributes)
        if not block:
            return
        part = self.next_part()
        if isinstance(getattr(self, part), list):
            getattr(self, part).append(block)
        else:
            setattr(self, part, block)

    def leave_l(self):
        # The default case, this is when there is no value for the
        # test.
        if self.test is None:
            self.test = ast.Name('False', ast.Load())

    def enter_script(self, name, qname, attributes):
        # Parse multiple blocks
        part = self.next_part()
        self.current_part = part
        setattr(self, part, [])

    def leave_script(self):
        self.current_part = None

    def leave_block(self):
        if not self.test:
            self.test = reportTrue(self)
        if not self.expr1:
            self.expr1 = [passBlock(self)]

    def to_ast(self):
        _if = ast.If(self.test.to_ast(),
                     [e.to_ast() for e in self.expr1],
                     [])
        return _if

builtin_parsers = {
    # Reports

    # Control
    # 'doWait': doWait,
    # 'doForever': doForever,
    # 'doRepeat': doRepeat,
    # 'doBroadcast': doBroadcast,
    # 'doBroadcastAndWait': doBroadcastAndWait,
    'doIf': doIf,
    # 'doIfElse': doIfElse,
    # 'doWaitUntil': doWaitUntil,
    # 'doUntil': doUntil,
    # 'doStop': doStop,
    # 'doStopAll': doStopAll,
    # NOTE: there are 3 forms of this in snap
    # 'doRun': doRun,
    # NOTE: there are 3 forms of this in snap
    # 'fork': fork,
    # NOTE: there are 3 forms of this in snap
    # 'evaluate': evaluate,
    # 'doReport': doReport,
    # 'doStopBlock': doStopBlock,

    #
    # Operators
    #
    # 'reportSum': reportSum,  # +
    # 'reportDifference': reportDifference,  # -
    # 'reportProduct': reportProduct,  # *
    # 'reportQuotient': reportQuotient,  # /
    # 'reportRandom': reportRandom,  # randomFrom:to:
    # 'reportLessThan': reportLessThan,  # <
    # 'reportEquals': reportEquals,  # =
    # 'reportGreaterThan': reportGreaterThan,  # >
    # 'reportAnd': reportAnd,  # &
    # 'reportOr': reportOr,  # |
    # 'reportNot': reportNot,  # not
    'reportTrue': reportTrue,  # getTrue
    # 'reportFalse': reportFalse,  # getFalse
    # 'reportJoinWords': reportJoinWords,  # concatenate:with:
    # 'reportLetter': reportLetter,  # letter:of:
    # 'reportStringSize': reportStringSize,  # stringLength:
    # 'reportUnicode': reportUnicode,  # asciiCodeOf
    # 'reportUnicodeAsLetter': 'reportUnicodeAsLetter',  # asciiLetter
    # 'reportModulus': reportModulus,  # \\\\
    # 'reportRound': reportRound,  # rounded
    # 'reportMonadic': reportMonadic,  # computeFunction:of:
    # 'reportIsA': reportIsA,  # isObject:type:

    #
    # Variables
    #
    'doSetVar': doSetVar,
    # 'doChangeVar': doChangeVar,
    # 'doShowVar': doShowVar,
    # 'doHideVar': doHideVar,
    'doDeclareVariables': doDeclareVariables,
    'reportNewList': reportNewList,
    # 'doAddToList': doAddToList,
    # 'doDeleteFromList': doDeleteFromList,
    # 'doInsertInList': doInsertInList,
    # 'doReplaceInList': doReplaceInList,
    # 'reportListItem': reportListItem,
    # 'reportListLength': reportListLength,
    # 'reportListContainsItem': reportListContainsItem,

    #
    # Kludge
    #
    # 'doWarp': doWarp
}


def enter_noop(name, qname, attributes):
    pass


def leave_noop():
    pass


def enter(object, name):
    if hasattr(object, 'enter_' + name):
        return getattr(object, 'enter_' + name)
    else:
        LOG.debug("Unparsable element %s", name)
        return enter_noop


def leave(object, name):
    if hasattr(object, 'leave_' + name):
        return getattr(object, 'leave_' + name)
    else:
        LOG.debug("Unparsable element %s", name)
        return leave_noop


class BlockParser(ContentHandler):

    def __init__(self):
        self.name = ''
        self.app = ''
        self.version = ''
        self.parser_stack = []

    def getParser(self):
        for parser in reversed(self.parser_stack):
            if isinstance(parser, (str, tuple)):
                continue
            return parser
        return self

    def pushParser(self, parser):
        self.parser_stack.append(parser)
        return parser

    def popParser(self):
        return self.parser_stack.pop()

    def startElementNS(self, name, qname, attributes):
        qname = qname.replace('-', '_')
        enter(self.getParser(), qname)(name, qname, attributes)

    def endElementNS(self, name, qname):
        qname = qname.replace('-', '_')
        leave(self.getParser(), qname)()

    def characters(self, data):
        if self.getParser() != self:
            self.getParser().characters(data)

    def enter_project(self, name, qname, attributes):
        self.name = attributes.getValueByQName('name')
        self.app = attributes.getValueByQName('app')
        self.version = attributes.getValueByQName('version')

    def enter_scripts(self, name, qname, attributes):
        # The main functions
        print 'block', qname

    def enter_blocks(self, name, qname, attributes):
        # Collection of custom blocks
        pass

    def enter_block_definition(self, name, qname, attributes):
        # Define custom block
        # print 'block', qname
        pass

    def enter_block(self, name, qname, attributes):
        self.parser_stack.append(name)
        # Call builtin
        fn = (attributes.getValueByQName('s')
              if attributes.has_key((None, 's')) else '')
        if fn in builtin_parsers:
            self.parser_stack.append(builtin_parsers[fn](self))
        else:
            self.parser_stack.append(qname)

        if attributes.has_key('var'):
            # Return a variable?
            pass

    def leave_block(self):
        pass

    def enter_custom_block(self, name, qname, attributes):
        # Call function or is this like a macro?
        # print 'block', qname
        # print attributes.getValueByQName('s')
        pass


def parse(filename):
    tree = lxml.etree.parse(open(filename))
    handler = BlockParser()
    lxml.sax.saxify(tree, handler)
    return handler
