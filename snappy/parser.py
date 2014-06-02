import ast
import codegen
import copy
import re
import itertools
from StringIO import StringIO

import lxml.etree
import lxml.sax
import logging
from xml.sax.handler import ContentHandler

LOG = logging.getLogger(__name__)

LAST = -1

SCRIPT_HEADER = """

import logging
import collections

LOG = logging.getLogger(__file__)
logging.basicConfig(level=logging.DEBUG)
LOG.info('Started')

_report = {}

def _doReport(result, name):
    LOG.debug('Result: %s %s' % (name, result))
    _report['result'] = (name, result)
    return result

def _dumpReport():
    import json
    import os
    result_file = os.path.join(os.path.dirname(__file__), 'result.json')
    result = open(result_file, 'w')
    result.write(json.dumps(_report['result']))

"""

SCRIPT_FOOTER = """
_dumpReport()
LOG.info('Finished')
"""


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
        state = find_first(self, path)
        if not state:
            raise Exception("Couldn't find element")
        return state

    def __repr__(self):
        return "<Block name='%s' %s>" % (self.block_name, self.attributes)


class Block(BaseBlock):
    pass


class NotImplementedBlock(Block):
    def to_ast(self, ctx):
        raise Exception("%s block isn't implemented" % self.attributes['s'])


class NamedBlock(Block):

    def __init__(self, name, qname, attributes):
        super(NamedBlock, self).__init__(name, qname, attributes)
        self.block_name = attributes['var']

    def to_ast(self, ctx):
        if ctx.function and self.block_name in ctx.function.function_arguments:
            return ast.Name(self.block_name, ast.Load())
        if self.block_name not in ctx.variables:
            return ast.Name(self.block_name, ast.Load())
        name = ast.Name('_vars', ast.Load())
        index = ast.Index(ast.Str(self.block_name))
        var = ast.Subscript(name, index, ast.Load())
        return var


class LiteralBlock(Tag):

    def to_ast(self, ctx):
        try:
            value = ast.Num(int(self.text))
        except:
            value = ast.Str(self.text)
        return value

    def to_name(self):
        value = ast.Name(self.text, ast.Load())
        return value


class Option(Tag):

    def __repr__(self):
        return "<Option name='%s' %s>" % (self.name, self.attributes)


class Input(Tag):

    @property
    def type(self):
        return self.attributes['type']


class PassBlock(Block):

    # TODO this block has an inconsistent definition because it's not
    # called directly by the parser.  This should probably be changed.
    def __init__(self):
        self.name = "Pass"
        self.attributes = {}
        self.children = []

    def to_ast(self, ctx):
        return ast.Pass()


class reportTrue(Block):

    def to_ast(self, ctx):
        # NOTE needs to be wrapped it a ast.Expr([]) in some cases.
        return ast.Name('True', ast.Load())


class reportNot(Block):

    def to_ast(self, ctx):
        return ast.UnaryOp(ast.Not(), self.children[0].to_ast(ctx))


class reportAnd(Block):

    def to_ast(self, ctx):
        return ast.BoolOp(ast.And(), [v.to_ast(ctx) for v in self.children])


class operatorBlock(Block):
    operator = None

    def to_ast(self, ctx):
        assert self.operator
        return ast.Compare(self.children[0].to_ast(ctx),
                           [self.operator()],
                           [self.children[1].to_ast(ctx)])


class reportEquals(operatorBlock):
    operator = ast.Eq


class reportGreaterThan(operatorBlock):
    operator = ast.Gt


class reportLessThan(operatorBlock):
    operator = ast.Lt


class reportNewList(Block):

    def to_ast(self, ctx):
        variables = self.find_child(['list'])
        return ast.List([v.to_ast(ctx) for v in variables.children],
                        ast.Load())


class reportJoinWords(Block):

    def to_ast(self, ctx):
        args = self.children[0].children
        left = args[0].to_ast(ctx)
        for right in args[1:]:
            right = right.to_ast(ctx)
            left = ast.BinOp(left, ast.Add(), right)
        return left


class reportLetter(Block):

    def to_ast(self, ctx):
        index = ast.Index(ast.BinOp(self.children[0].to_ast(ctx),
                                    ast.Sub(), ast.Num(1)))
        variable = self.children[1].to_ast(ctx)
        return ast.Subscript(variable, index, ast.Load())


class reportStringSize(Block):

    def to_ast(self, ctx):
        value = self.children[0].to_ast(ctx)
        args = [value]
        func = ast.Name('len', ast.Load())
        return ast.Call(func, args, [], None, None)


class doInsertInList(Block):

    def to_ast(self, ctx):
        value = self.children[0].to_ast(ctx)
        options = [o.text for o in self.children[1].children
                   if isinstance(o, Option)]
        var = self.children[2].to_ast(ctx)
        if '1' in options:
            args = [ast.Num(0), value]
            func = ast.Attribute(value=var, attr='insert')
        else:  # This covers 'last' and 'any' cases
            args = [value]
            func = ast.Attribute(value=var, attr='append')
        return ast.Call(func, args, [], None, None)


class doAddToList(Block):

    def to_ast(self, ctx):
        value = self.children[0].to_ast(ctx)
        var = self.children[1].to_ast(ctx)
        args = [value]
        func = ast.Attribute(value=var, attr='append')
        return ast.Call(func, args, [], None, None)


class doSetVar(Block):

    def to_ast(self, ctx):
        var = self.children[0].text
        if ctx.function and var in ctx.function.function_arguments:
            var = ast.Name(var, ast.Load())
        else:
            name = ast.Name('_vars', ast.Load())
            index = ast.Index(self.children[0].to_ast(ctx))
            var = ast.Subscript(name, index, ast.Load())
        return ast.Assign([var], self.children[1].to_ast(ctx))


class doChangeVar(Block):

    def to_ast(self, ctx):
        name = self.children[0].to_name()
        change = ast.BinOp(name, ast.Add(), self.children[1].to_ast(ctx))
        return ast.Assign([name], change)


class doDeclareVariables(Block):

    def to_ast(self, ctx):
        variables = self.find_child(['list'])
        ctx.variables.extend([v.text for v in variables])
        return None


class doReport(Block):

    def to_ast(self, ctx):
        func = ast.Name('_doReport', ast.Load())
        args = [self.children[0].to_ast(ctx),
                ast.Str(ctx.function.function_name)]
        return ast.Return(ast.Call(func, args, [], None, None))


class doIf(Block):

    def to_ast(self, ctx):
        _if = ast.If(self.children[0].to_ast(ctx),
                     self.children[1].to_ast(ctx),
                     [])
        return _if


class doIfElse(Block):

    def to_ast(self, ctx):
        _if = ast.If(self.children[0].to_ast(ctx),
                     self.children[1].to_ast(ctx),
                     self.children[2].to_ast(ctx))
        return _if


class Evaluate(Block):

    def to_ast(self, ctx):
        # TODO add argument support
        assert not self.find_child(['list']).children, "Evaluate with arguments, isn't supported."
        args = []
        func = self.children[0].to_ast(ctx)
        func_name = self.children[0].block_name
        # If the thing being evaluated was passed in as an argument.
        # Then call it with all the args from the that were passed
        # into this function.
        if func_name in ctx.function.function_arguments:
            args = [ast.Name(arg, ast.Load())
                    for arg in ctx.function.function_arguments]
            return ast.Call(func, args, [], None, None)
        return ast.Call(func, args, [], None, None)


class doUntil(Block):

    def to_ast(self, ctx):
        _while = ast.While(
            ast.UnaryOp(ast.Not(), self.children[0].to_ast(ctx)),
            self.children[1].to_ast(ctx),
            []
        )
        return _while


class doForEach(Block):

    def to_ast(self, ctx):
        _for = ast.For(self.children[0].to_name(),
                       self.children[1].to_ast(ctx),
                       self.children[2].to_ast(ctx),
                       [])
        return _for


class doWarp(Block):

    def to_ast(self, ctx):
        return self.children[0].to_ast(ctx)


class Autolambda(Block):

    def to_ast(self, ctx):
        args = ast.arguments([], None, None, [])
        return ast.Lambda(args, self.children[0].to_ast(ctx))


class Reify(Block):

    def to_ast(self, ctx):
        # TODO this isn't the correct implementation, but i have no
        # idea what ringification actually does.  It looks like it's
        # just thing or empty list, but I'm not sure
        return self.children[0].to_ast(ctx)


class Script(BaseBlock):

    def has_body(self):
        return bool(self.children)

    def inline_node(self, node):
        if node.__class__ not in [ast.FunctionDef, ast.For, ast.While, PassBlock]:
            return ast.Expr(node)
        else:
            return node

    def to_ast(self, ctx):
        return [self.inline_node(e.to_ast(ctx))
                for e in self.children or [PassBlock()]
                if e]


class BlockDefinition(BaseBlock):

    def __init__(self, name, qname, attributes):
        super(BlockDefinition, self).__init__(name, qname, attributes)
        self.block_name = attributes['s']
        self.type = attributes['type']
        self.category = attributes['category']
        self.inner_functions = []

    def to_ast(self, ctx):
        ctx = ctx.copy()
        ctx.function = self
        name = self.function_name
        args = ast.arguments([ast.Name(arg, ast.Load())
                              for arg in self.function_arguments],
                             None, None, [])
        script = self.find_child(['script'])
        script_ast = script.to_ast(ctx)
        vars = ast.Assign([ast.Name('_vars', ast.Load())], ast.Dict([], []))

        if script.has_body():
            # Put any inner functions at the start of the body.  This has
            # to happen after the body has been evaluated.
            body = [ast.Expr(vars)] + self.inner_functions + script_ast
        else:
            body = script_ast
        return ast.FunctionDef(name, args, body, [])

    def custom_block_id(self):
        inputs = list(reversed(self.function_argument_types))
        name_parts = []
        for a in self.block_name.split(' '):
            if a.startswith('%'):
                name_parts.append(inputs.pop())
            else:
                name_parts.append(a)
        return ' '.join(name_parts)

    @property
    def function_name(self):
        fn = re.sub('[^0-9a-zA-Z]+', '_', str(self.block_name))
        return fn

    @property
    def function_arguments(self):
        args = [a[1:].strip("'") for a in self.block_name.split(' ')
                if a.startswith('%')]
        return args

    @property
    def function_argument_types(self):
        return [i.type for i in self.find_child(['inputs']).children]

    def function_argument_type(self, arg):
        return dict(zip(self.children, func.function_argument_types))[arg]


class CustomBlock(BaseBlock):
    counter = itertools.count().next

    def __init__(self, name, qname, attributes):
        super(CustomBlock, self).__init__(name, qname, attributes)
        self.block_name = attributes['s']

    def to_func(self, ctx, func, body):
        """Append the custom block as a function into the parent functions
        scope."""
        func_name = 'custom_block_' + str(self.counter())
        args = ast.arguments([ast.Name(arg, ast.Load())
                              for arg in func.function_arguments],
                             None, None, [])
        ctx.function.inner_functions.append(
            ast.FunctionDef(func_name, args, body, []))
        return func_name

    def to_ast(self, ctx):
        # TODO This is probably broken
        func = ctx.lookupCustomBlock(self.block_name)
        args = []
        for arg, type in zip(self.children, func.function_argument_types):
            arg_ast = arg.to_ast(ctx)
            if type == '%cs':
                name = self.to_func(ctx, func, arg_ast)
                args.append(ast.Name(name, ast.Load()))
            else:
                args.append(arg_ast)

        return ast.Call(ast.Name(func.function_name, ast.Load()),
                        args, [], None, None)


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
    'option': Option,
    'list': Tag,
    'script': Script,
    'block': block_handler,
    'custom-block': CustomBlock,
    'block-definition': BlockDefinition,
    'autolambda': Autolambda,
    'input': Input,
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
    'doIfElse': doIfElse,
    # 'doWaitUntil': doWaitUntil,
    'doUntil': doUntil,
    # 'doStop': doStop,
    # 'doStopAll': doStopAll,
    # NOTE: there are 3 forms of this in snap
    'doRun': Evaluate,
    # NOTE: there are 3 forms of this in snap
    # 'fork': fork,
    # NOTE: there are 3 forms of this in snap
    'evaluate': Evaluate,
    'doReport': doReport,
    # 'doStopBlock': doStopBlock,

    #
    # Ringify things
    #
    'reifyReporter': Reify,
    'reifyScript': Reify,

    #
    # Operators
    #
    # 'reportSum': reportSum,  # +
    # 'reportDifference': reportDifference,  # -
    # 'reportProduct': reportProduct,  # *
    # 'reportQuotient': reportQuotient,  # /
    # 'reportRandom': reportRandom,  # randomFrom:to:
    'reportLessThan': reportLessThan,  # <
    'reportEquals': reportEquals,  # =
    'reportGreaterThan': reportGreaterThan,  # >
    'reportAnd': reportAnd,  # &
    # 'reportOr': reportOr,  # |
    'reportNot': reportNot,  # not
    'reportTrue': reportTrue,  # getTrue
    # 'reportFalse': reportFalse,  # getFalse
    'reportJoinWords': reportJoinWords,  # concatenate:with:
    'reportLetter': reportLetter,  # letter:of:
    'reportStringSize': reportStringSize,  # stringLength:
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
    'doChangeVar': doChangeVar,
    # 'doShowVar': doShowVar,
    # 'doHideVar': doHideVar,
    'doDeclareVariables': doDeclareVariables,
    'reportNewList': reportNewList,
    'doAddToList': doAddToList,
    # 'doDeleteFromList': doDeleteFromList,
    'doInsertInList': doInsertInList,
    # 'doReplaceInList': doReplaceInList,
    # 'reportListItem': reportListItem,
    # 'reportListLength': reportListLength,
    # 'reportListContainsItem': reportListContainsItem,

    #
    # Kludge
    #
    'doWarp': doWarp,

    #
    # Edgy
    #
    'doForEach': doForEach,
}


class Context():
    def __init__(self, custom_blocks=None, function=None, module=None,
                 used_custom_blocks=None):
        self.custom_blocks = custom_blocks
        self.function = function
        self.module = module
        self.variables = []
        self.used_custom_blocks = used_custom_blocks

    def lookupCustomBlock(self, name):
        if name not in self.used_custom_blocks:
            self.used_custom_blocks.append(name)
        return self.custom_blocks[name]

    def copy(self):
        kwargs = vars(self)
        if 'variables' in kwargs:
            del kwargs['variables']
        return Context(**kwargs)


class BlockParser(ContentHandler):

    def __init__(self):
        self.name = ''
        self.app = ''
        self.version = ''
        self.stack = []
        self._custom_blocks = None
        self.children = []
        self._scripts = []

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
        self.current_tag = None
        if self.stack:
            self.popT(qname)

    def characters(self, data):
        if not hasattr(self, 'current_tag'):
            return
        if data and isinstance(self.current_tag, (Option, LiteralBlock)):
            self.current_tag.children.append(data)

    def scripts(self, ctx):
        scripts = find_first(self, ['project', 'stage', 'sprites',
                                    'sprite', 'scripts'])
        if not scripts:
            return []

        if self._scripts:
            return self._scripts

        counter = itertools.count().next
        args = ast.arguments([], None, None, [])

        self._scripts = [ast.FunctionDef('main_' + str(counter()),
                                         args, script.to_ast(ctx), [])
                         for script in scripts.children or [PassBlock()]]

        return self._scripts

    @property
    def custom_blocks(self):
        if self._custom_blocks:
            return self._custom_blocks
        blocks = find_first(self, ['project', 'blocks'])
        if not blocks:
            return {}
        self._custom_blocks = dict([(block.custom_block_id(), block)
                                    for block in blocks.children])
        return self._custom_blocks

    def create_context(self, module=None):
        return Context(custom_blocks=self.custom_blocks, used_custom_blocks=[])

    def to_ast(self, ctx, main_func=None):
        script = ast.parse(SCRIPT_HEADER)
        script_footer = ast.parse(SCRIPT_FOOTER)
        body = script.body
        ctx = self.create_context(module=script)
        body.extend(self.scripts(ctx))

        # Try and add custom blocks
        for block in self.custom_blocks.values():
            try:
                block_ast = block.to_ast(ctx)
            except Exception as e:
                # LOG.exception(e)
                LOG.debug("Failed to generate function for %s" % block.block_name)
            else:
                body.append(block_ast)
        if main_func:
            body.append(
                ast.Expr(
                    ast.Call(
                        ast.Name(main_func, ast.Load()),
                        [], [], None, None)))

        script.body.extend(script_footer.body)
        return script


def parse(filename):
    tree = lxml.etree.parse(open(filename))
    handler = BlockParser()
    lxml.sax.saxify(tree, handler)
    return handler

def parses(string):
    tree = lxml.etree.parse(StringIO(string))
    handler = BlockParser()
    lxml.sax.saxify(tree, handler)
    return handler
