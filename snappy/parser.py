import ast
import codegen
import copy
import re

import lxml.etree
import lxml.sax
import logging
from xml.sax.handler import ContentHandler

LOG = logging.getLogger(__name__)

LAST = -1


def find_closest(state, rstack):
    if state and rstack:
        if state[LAST].name == rstack[0]:
            rstack = rstack[1:]
            if rstack:
                state = state[LAST].children
                return find_closest(state, rstack)
            else:
                return state[LAST], rstack
        else:
            return state, rstack
    else:
        return state, rstack


def find_first(node, rstack):
    """Traverse the nodes and find the first node that
    matches the context listed in rstack."""
    node_name = rstack[0]
    remainder = rstack[1:]
    for child in node.children:
        if child.name == node_name:
            if remainder:
                return find_first(child, remainder)
            return child


class Tag(object):

    def __init__(self, name, qname, attributes):
        self.name = qname
        self.attributes = attributes
        self.children = []

    def __getitem__(self, item):
        return self.children.__getitem__(item)

    @property
    def text(self):
        """Return all the text children as a string"""
        return ''.join([child for child in self.children
                        if isinstance(child, (str, unicode))])

    def __repr__(self):
        return "<Tag name='%s' %s>" % (self.name, self.attributes)

    def __str__(self):
        return self.text


class BaseBlock(Tag):

    def __init__(self, name, qname, attributes):
        super(BaseBlock, self).__init__(name, qname, attributes)
        self.block_name = self.__class__.__name__
        self.stack = []

    def find_child(self, path):
        state, remainder = find_closest(self.children, path)
        if remainder:
            raise Exception("Couldn't find element")
        return state

    def to_python(self):
        return str(codegen.to_source(self.to_ast()))

    def __repr__(self):
        return "<Block name='%s' %s>" % (self.block_name, self.attributes)


class Block(BaseBlock):
    pass


class NotImplementedBlock(Block):
    pass


class NamedBlock(Block):

    def __init__(self, name, qname, attributes):
        super(NamedBlock, self).__init__(name, qname, attributes)
        self.block_name = attributes['var']

    def to_ast(self):
        return ast.Name(self.block_name, ast.Load())


class LiteralBlock(Tag):

    def to_ast(self):
        try:
            value = ast.Num(int(self.text))
        except:
            value = ast.Str(self.text)
        return value

    def to_name(self):
        value = ast.Name(self.text, ast.Load())
        return value


class PassBlock(Block):

    # TODO this block has an inconsistent definition because it's not
    # called directly by the parser.  This should probably be changed.
    def __init__(self):
        self.name = "Pass"
        self.attributes = {}
        self.children = []

    def to_ast(self):
        return ast.Expr([ast.Name('Pass', ast.Load())])


class reportTrue(Block):

    def to_ast(self):
        # NOTE needs to be wrapped it a ast.Expr([]) in some cases.
        return ast.Name('True', ast.Load())


class reportNewList(Block):

    def to_ast(self):
        variables = self.find_child(['list'])
        return ast.List([v.to_ast() for v in variables.children], ast.Load())


class doSetVar(Block):

    def to_ast(self):
        name = [self.children[0].to_name()]
        return ast.Assign(name, self.children[1].to_ast())


class doDeclareVariables(Block):

    def to_ast(self):
        variables = self.find_child(['list'])
        names = ast.Tuple([ast.Name(var.text, ast.Load())
                          for var in variables],
                          ast.Load())
        values = ast.Tuple([ast.Name('None', ast.Load())
                            for var in variables],
                           ast.Load())
        assign = ast.Assign([names], values)
        return assign


class doIf(Block):

    def to_ast(self):
        _if = ast.If(self.children[0].to_ast(),
                     self.children[1].to_ast(),
                     [])
        return _if


class Script(BaseBlock):

    def to_ast(self):
        return [e.to_ast() for e in self.children or [PassBlock()]]


class BlockDefinition(BaseBlock):

    def __init__(self, name, qname, attributes):
        super(BlockDefinition, self).__init__(name, qname, attributes)
        self.block_name = attributes['s']
        self.type = attributes['type']
        self.category = attributes['category']

    def to_ast(self):
        body = self.find_child(['script']).to_ast()
        name = self.function_name
        args = ast.arguments([ast.Name(arg, ast.Load())
                              for arg in self.function_arguments],
                             None, None, [])
        return ast.FunctionDef(name, args, body, [])

    @property
    def function_name(self):
        fn = re.sub('[^0-9a-zA-Z]+', '_', str(self.block_name))
        return fn

    @property
    def function_arguments(self):
        args = [a[1:].strip("'") for a in self.block_name.split(' ')
                if a.startswith('%')]
        return args


class CustomBlock(BaseBlock):

    def __init__(self, name, qname, attributes):
        super(CustomBlock, self).__init__(name, qname, attributes)
        self.block_name = attributes['s']

    def to_ast(self):
        return self.lookupCustomBlock(self.block_name)


def block_handler(name, qname, attributes):
    # Handle expressions
    fn = attributes.get('s')
    if fn:
        block_parser = builtin_blocks.get(fn, NotImplementedBlock)(name, qname, attributes)
        return block_parser

    # Handle variables
    var = attributes.get('var')
    if var:
        block_parser = NamedBlock(name, qname, attributes)
        return block_parser
    raise Exception('Unknown block type.')


tag_parsers = {
    'l': LiteralBlock,
    'list': Tag,
    'script': Script,
    'block': block_handler,
    'custom-block': CustomBlock,
    'block-definition': BlockDefinition,
}

builtin_blocks = {
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


class BlockParser(ContentHandler):

    def __init__(self):
        self.name = ''
        self.app = ''
        self.version = ''
        self.stack = []
        self._custom_blocks = None
        self.children = []

    def lookupCustomBlock(self, name):
        return self.custom_blocks[name]

    def pushT(self, tag):
        self.current_tag = tag
        state, stack = find_closest(self.children, copy.copy(self.stack))
        self.stack.append(tag.name)
        if len(self.stack) == 1:
            self.children.append(self.current_tag)
        else:
            state.children.append(self.current_tag)
        return tag

    def popT(self, tag=None):
        tag1 = self.stack.pop()
        if tag:
            if isinstance(tag, (str, unicode)):
                name = tag
            else:
                name = tag.name
            if issubclass(tag1.__class__, Block):
                tag1 = 'block'
            assert name == tag1, "Tag stack mismatch %r != %r" % (tag, tag1)
        return tag

    def startElementNS(self, name, qname, attributes):
        attributes = dict([(attributes.getQNameByName(k), v)
                           for k, v in attributes.items()])
        tag = tag_parsers.get(qname, Tag)(name, qname, attributes)
        self.pushT(tag)
        return tag

    def endElementNS(self, name, qname):
        if self.stack:
            self.popT(qname)

    def characters(self, data):
        data = data.strip()
        if hasattr(self, 'current_tag') and data:
            self.current_tag.children.append(data)

    @property
    def scripts(self):
        scripts = find_first(self, ['project', 'stage', 'sprites',
                                    'sprite', 'scripts'])
        if scripts:
            return scripts.children
        return []

    @property
    def custom_blocks(self):
        if self._custom_blocks:
            return self._custom_blocks
        blocks = find_first(self, ['project', 'blocks'])
        if not blocks:
            return {}
        self._custom_blocks = dict([(block.block_name, block)
                                    for block in blocks.children])
        return self._custom_blocks


def parse(filename):
    tree = lxml.etree.parse(open(filename))
    handler = BlockParser()
    lxml.sax.saxify(tree, handler)
    return handler
