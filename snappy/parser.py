import ast
import codegen
import copy

import lxml.etree
import lxml.sax
import logging
from xml.sax.handler import ContentHandler

LOG = logging.getLogger(__name__)

NAME = 0
LAST = -1
ATTRIBUTES = 1
CHILDREN = 2


def find_closest(state, rstack):
    if state:
        if isinstance(state[LAST], tuple) and state[LAST][NAME] == rstack[NAME]:
            rstack = rstack[1:]
            if rstack:
                state = state[LAST][CHILDREN]
                return find_closest(state, rstack)
            else:
                return state[LAST], rstack
        else:
            return state, rstack
    else:
        return state, rstack


class BaseBlock(object):

    _text_buffer = ''

    def __init__(self, parser):
        self.parser = parser
        self.stack = []
        # The state attribute store the contents of the blocks tags.
        # [('tagname', 'attributes', [values, 'and bodies']))]
        self.state = []

    def setup(self, name, qname, attributes):
        self.stack = [qname]
        self.current_tag = (qname, attributes.items(), [])
        self.state = [self.current_tag]
        return self

    def pushObject(self, object):
        self.current_tag[CHILDREN].append(object)

    def pushT(self, tag, name, qname, attributes):
        self.stack.append(tag)
        self.current_tag = (qname, attributes.items(), [])
        state, stack = find_closest(self.state, copy.copy(self.stack))
        if stack:
            state.append(self.current_tag)
        else:
            state[CHILDREN].append(self.current_tag)
        return tag

    def popT(self, tag=None):
        tag1 = self.stack.pop()
        # TODO: currently doesn't assert tags that are objects
        if tag:
            assert tag == tag1, "Tag stack mismatch %r != %r" % (tag, tag1)
        return tag

    def pushParser(self, parser):
        """Push a block parser onto the parser stack."""
        return self.parser.pushParser(parser)

    def popParser(self):
        """Pop a block parser from the parser stack."""
        popped = self.parser.popParser()
        return popped

    def registerCustomBlock(self, block):
        return self.parser.registerCustomBlock(block)

    def enter_block(self, name, qname, attributes):
        # Handle expressions
        fn = (attributes.getValueByQName('s')
              if attributes.has_key((None, 's')) else '')
        if fn:
            block_parser = builtin_parsers.get(fn, NotImplementedBlock)(self)
            block_parser.setup(name, qname, attributes)
            self.pushObject(block_parser)
            return self.pushParser(block_parser)

        # Handle variables
        var = (attributes.getValueByQName('var')
              if attributes.has_key((None, 'var')) else '')
        if var:
            block_parser = namedBlock(self)
            block_parser.setup(name, qname, attributes)
            self.pushObject(block_parser)
            return self.pushParser(block_parser)

    def leave_block(self):
        parser = self.popParser()
        assert issubclass(parser.__class__, Block), parser.__class__.__name__
        return parser

    def enter_script(self, name, qname, attributes):
        parser = self.pushParser(Script(self))
        parser.setup(name, qname, attributes)
        self.pushObject(parser)

    def leave_script(self):
        parser = self.popParser()
        assert parser.__class__.__name__ == 'Script', parser.__class__.__name__
        return parser

    def enter_block_definition(self, name, qname, attributes):
        raise Exception("Should not be defining custom blocks from within a block.")

    def leave_block_definition(self):
        parser = self.popParser()
        assert parser.__class__.__name__ == 'BlockDefinition', parser.__class__.__name__
        return parser

    def enter_custom_block(self, name, qname, attributes):
        parser = self.pushParser(CustomBlock(self))
        parser.setup(name, qname, attributes)
        self.pushObject(parser)

    def leave_custom_block(self):
        parser = self.popParser()
        assert parser.__class__.__name__ == 'CustomBlock', parser.__class__.__name__
        return parser

    # Tags
    def enter_l(self, name, qname, attributes):
        self.pushT('l', name, qname, attributes)

    def leave_l(self):
        self.popT('l')

    def enter_list(self, name, qname, attributes):
        self.pushT('list', name, qname, attributes)

    def leave_list(self):
        self.popT('list')

    def enter_option(self, name, qname, attributes):
        self.pushT('option', name, qname, attributes)

    def leave_option(self):
        self.popT('option')

    def characters(self, data):
        data = data.strip()
        if hasattr(self, 'current_tag') and data:
            self.current_tag[2].append(data)
        self._text_buffer = data

    def __str__(self):
        return str(codegen.to_source(self.to_ast()))


class Block(BaseBlock):
    pass


class NotImplementedBlock(Block):
    pass


class namedBlock(Block):

    def setup(self, name, qname, attributes):
        var = attributes.getValueByQName('var')
        self.name = var

    def to_ast(self):
        return ast.Name(self.name, ast.Load())


class literalBlock(Block):

    # TODO this has an inconsistent calling convention.  is there a
    # way to use the enter_block method to parse the value?
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
        super(reportNewList, self).leave_l()
        self.values.append(literalBlock(self._text_buffer))

    def to_ast(self):
        return ast.List([v.to_ast() for v in self.values], ast.Load())


class doSetVar(Block):
    def __init__(self, parser):
        super(doSetVar, self).__init__(parser)
        self.variable = None
        self.value = None

    def leave_l(self):
        super(doSetVar, self).leave_l()
        if not self.variable:
            self.variable = self._text_buffer
        elif not self.value:
            self.value = literalBlock(self._text_buffer)

    def enter_block(self, name, qname, attributes):
        block = super(doSetVar, self).enter_block(name, qname, attributes)
        self.value = block

    def to_ast(self):
        name = [ast.Name(self.variable, ast.Load())]
        return ast.Assign(name, self.value.to_ast())


class doDeclareVariables(Block):

    def __init__(self, parser):
        super(doDeclareVariables, self).__init__(parser)
        self.variables = []

    def leave_l(self):
        super(doDeclareVariables, self).leave_l()
        self.variables.append(self._text_buffer)

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
        raise Exception("Lost position in if statement")

    def enter_block(self, name, qname, attributes):
        block = super(doIf, self).enter_block(name, qname, attributes)
        part = self.next_part()
        if isinstance(getattr(self, part), list):
            getattr(self, part).append(block)
        else:
            setattr(self, part, block)

    def leave_l(self):
        # The default case, this is when there is no value for the
        # test.
        super(doIf, self).leave_l('l')
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
        super(doIf, self).leave_block()
        if not self.test:
            self.test = reportTrue(self)
        if not self.expr1:
            self.expr1 = [passBlock(self)]

    def to_ast(self):
        _if = ast.If(self.test.to_ast(),
                     [e.to_ast() for e in self.expr1],
                     [])
        return _if


class Script(BaseBlock):
    def __init__(self, parser):
        super(Script, self).__init__(parser)
        self.exprs = []

    def enter_block(self, name, qname, attributes):
        block = super(Script, self).enter_block(name, qname, attributes)
        self.exprs.append(block)
        return block

    def to_ast(self):
        return [e.to_ast() for e in self.exprs]


class BlockDefinition(BaseBlock):
    name = None
    type = None
    category = None
    script = None

    def setup(self, name, qname, attributes):
        self.name = attributes.getValueByQName('s')
        self.type = attributes.getValueByQName('type')
        self.category = attributes.getValueByQName('category')

    def enter_script(self, name, qname, attributes):
        parser = self.pushParser(Script(self))
        parser.setup(name, qname, attributes)


class CustomBlock(BaseBlock):
    name = None

    def setup(self, name, qname, attributes):
        super(CustomBlock, self).setup(name, qname, attributes)
        self.name = attributes.getValueByQName('s')

    def to_ast(self):
        return self.lookupCustomBlock(self.name)


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
        self.scripts = []
        self.custom_blocks = {}

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
        popped = self.parser_stack.pop()
        return popped

    def registerCustomBlock(self, block):
        self.custom_blocks[block.name] = block
        return block

    def lookupCustomBlock(self, name):
        return self.custom_blocks[name]

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
        # Collection of custom scripts
        pass

    def enter_script(self, name, qname, attributes):
        parser = self.pushParser(Script(self))
        # Register top level scripts
        self.scripts.append(parser)
        return parser.setup(name, qname, attributes)

    def enter_blocks(self, name, qname, attributes):
        # Collection of custom blocks
        pass

    def enter_block_definition(self, name, qname, attributes):
        parser = self.pushParser(BlockDefinition(self))
        return parser.setup(name, qname, attributes)

    def enter_custom_block(self, name, qname, attributes):
        parser = self.pushParser(CustomBlock(self))
        return parser.setup(name, qname, attributes)


def parse(filename):
    tree = lxml.etree.parse(open(filename))
    handler = BlockParser()
    lxml.sax.saxify(tree, handler)
    return handler
