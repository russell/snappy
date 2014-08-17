import ast
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
from snappy import stdlib

logging.basicConfig(level=logging.DEBUG)
if '__file__' in locals():
    LOG = logging.getLogger(__file__)
    LOG.info('Started')
else:
    LOG = logging.getLogger(__name__)

_globals = stdlib._globals

"""

SCRIPT_FOOTER = """

if '__file__' in locals():
    stdlib.dumpReport(__file__)
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


def stdlib_call(fn, args):
    module = ast.Name('stdlib', ast.Load())
    func = ast.Attribute(value=module, attr=fn, ctx=ast.Load())
    if not isinstance(args, list):
        args = [args]
    return ast.Call(func, args, [], None, None)


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


def read_variable(ctx, name):
    if ctx.is_local_variable(name):
        vname = ast.Name('_locals', ast.Load())
        index = ast.Index(ast.Str(name))
        var = ast.Subscript(vname, index, ast.Load())
        return var
    elif ctx.is_argument(name):
        return ast.Name(name, ast.Load())
    else:
        vname = ast.Name('_globals', ast.Load())
        index = ast.Index(ast.Str(name))
        var = ast.Subscript(vname, index, ast.Load())
        return var


def write_variable(ctx, name):
    if ctx.is_local_variable(name):
        vname = ast.Name('_locals', ast.Load())
        index = ast.Index(ast.Str(name))
        var = ast.Subscript(vname, index, ast.Store())
        return var
    elif ctx.is_argument(name):
        return ast.Name(name, ast.Store())
    else:
        vname = ast.Name('_globals', ast.Load())
        index = ast.Index(ast.Str(name))
        var = ast.Subscript(vname, index, ast.Store())
        return var


class NamedBlock(Block):

    def __init__(self, name, qname, attributes):
        super(NamedBlock, self).__init__(name, qname, attributes)
        self.block_name = attributes['var']

    def to_ast(self, ctx):
        return read_variable(ctx, self.block_name)


class LiteralBlock(Tag):

    def to_ast(self, ctx):
        try:
            value = ast.Num(int(self.text))
        except:
            value = ast.Str(self.text)
        return value

    def to_name(self, op=ast.Load()):
        value = ast.Name(self.text, op)
        return value


class List(Tag):

    def to_ast(self, ctx):
        return ast.List([v.to_ast(ctx)
                         for v in self.children],
                        ast.Load())


class Option(Tag):

    def __repr__(self):
        return "<Option name='%s' %s>" % (self.name, self.attributes)


class Input(Tag):

    @property
    def type(self):
        return self.attributes['type']


class BaseReporter(Block):

    def report_ast(self, ctx):
        return [c.to_ast(ctx)
                for c in self.children]

    def to_ast(self, ctx):
        return stdlib_call(self.__class__.__name__,
                           self.report_ast(ctx))


class reportTrue(BaseReporter):
    pass


class reportNot(BaseReporter):
    pass


class reportAnd(BaseReporter):
    pass


class reportEquals(BaseReporter):
    pass


class reportGreaterThan(BaseReporter):
    pass


class reportLessThan(BaseReporter):
    pass


class reportLetter(BaseReporter):
    pass


class reportNewList(BaseReporter):

    def report_ast(self, ctx):
        variables = self.find_child(['list'])
        return ast.List([v.to_ast(ctx)
                         for v in variables.children],
                        ast.Load())


class reportCAR(BaseReporter):
    pass


class reportCDR(BaseReporter):
    pass


class reportCONS(BaseReporter):
    pass


class reportJoinWords(BaseReporter):
    pass


class reportListItem(BaseReporter):
    pass


class reportStringSize(BaseReporter):
    pass


class doInsertInList(Block):

    def to_ast(self, ctx):
        value = self.children[0].to_ast(ctx)
        options = [o.text for o in self.children[1].children
                   if isinstance(o, Option)]
        var = self.children[2].to_ast(ctx)
        if '1' in options:
            args = [ast.Num(0), value]
            func = ast.Attribute(value=var, attr='insert', ctx=ast.Load())
        else:  # This covers 'last' and 'any' cases
            args = [value]
            func = ast.Attribute(value=var, attr='append', ctx=ast.Load())
        return ast.Call(func, args, [], None, None)


class doAddToList(Block):

    def to_ast(self, ctx):
        value = self.children[0].to_ast(ctx)
        var = self.children[1].to_ast(ctx)
        args = [value]
        func = ast.Attribute(value=var, attr='append', ctx=ast.Load())
        return ast.Call(func, args, [], None, None)


class doSetVar(Block):

    def to_ast(self, ctx):
        var = self.children[0].text
        return ast.Assign([write_variable(ctx, var)],
                          self.children[1].to_ast(ctx))


class doChangeVar(Block):

    def to_ast(self, ctx):
        name = self.children[0].text
        change = ast.BinOp(read_variable(ctx, name), ast.Add(),
                           self.children[1].to_ast(ctx))
        return ast.Assign([write_variable(ctx, name)], change)


class doDeclareVariables(Block):
    """Create script local variables."""

    def to_ast(self, ctx):
        variables = self.find_child(['list'])
        if ctx.function:
            ctx.function.local_variables.extend([v.text for v in variables])
        # TODO Could return an ast node like (var1, var2) = (None, None)
        return None


class doReport(BaseReporter):
    def to_ast(self, ctx):
        value = super(doReport, self).to_ast(ctx)
        return ast.Return(value)


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
    count = 0

    def args_variable(self):
        name = 'eval_' + str(self.count)
        Evaluate.count += 1
        storage = ast.Assign([ast.Name(name, ast.Store())],
                             ast.List([], ast.Load()))
        self.arg = ast.Name(name, ast.Load())
        return storage

    def add_argument(self, value):
        func = ast.Attribute(value=self.arg, attr='append', ctx=ast.Load())
        return ast.Expr(ast.Call(func, [value], [], None, None))

    def to_ast(self, ctx):
        ctx.body.append(self.args_variable())
        args = []
        func = self.children[0].to_ast(ctx)
        func_name = self.children[0].block_name
        for child in self.children[1].children:
            ctx.body.append(self.add_argument(child.to_ast(ctx)))

        # If the thing being evaluated was passed in as an argument.
        # Then call it with all the args from the that were passed
        # into this function.  This supports calling looping functions.
        if func_name in ctx.function.function_arguments:
            args = [ast.Name(arg, ast.Load())
                    for arg in ctx.function.function_arguments]
            return ast.Call(func, args, [], None, None)
        return ast.Call(func, args, [], self.arg, None)


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
        ctx.inherited_scope.append(self.children[0].text)
        _for = ast.For(self.children[0].to_name(ast.Store()),
                       self.children[1].to_ast(ctx),
                       self.children[2].to_ast(ctx),
                       [])
        return _for


class doWarp(Block):

    def to_ast(self, ctx):
        return self.children[0].to_ast(ctx)


class Autolambda(Block):

    def to_ast(self, ctx):
        return self.children[0].to_ast(ctx)


class Reify(Block):
    count = 0

    def gen_name(self):
        name = 'reify_' + str(self.count)
        Reify.count += 1
        return name

    def to_ast(self, ctx):
        name = self.gen_name()
        # TODO need to set the context variable here so that i can
        # flatten autolambda statements.
        ctx1 = ctx.copy()
        ctx1.inherited_scope.extend([c.text for c in self.children[1]])

        args = ast.arguments([ast.Name(arg.text, ast.Param())
                              for arg in self.children[1]],
                             None, None, [])
        if isinstance(self.children[0], Autolambda):
            body = [c.to_ast(ctx1) for c in self.children[0].children]
        else:
            body = self.children[0].to_ast(ctx1)
        if self.attributes['s'] == 'reifyReporter':
            body[-1] = ast.Return(body[-1])
        fn = ast.FunctionDef(name, args, body, [])
        ctx.body.append(fn)
        # TODO this isn't the correct implementation, but i have no
        # idea what ringification actually does.  It looks like it's
        # just thing or empty list, but I'm not sure
        return ast.Name(name, ast.Load())


class Script(BaseBlock):

    def has_body(self):
        return bool(self.children)

    def inline_node(self, node):
        if not node:
            return node
        if node.__class__ in [ast.FunctionDef, ast.For, ast.While,
                              ast.Pass, ast.Return, ast.If, ast.Assign]:
            return node
        else:
            return ast.Expr(node)

    def to_ast(self, ctx):
        ctx = ctx.copy()
        ctx.body = []
        for node in self.children:
            node_ast = node.to_ast(ctx)
            r_node = self.inline_node(node_ast)
            if not r_node:
                continue
            if isinstance(node_ast, list):
                ctx.body.extend(node_ast)
            else:
                ctx.body.append(r_node)
        body = ctx.popBody()
        return body or [ast.Pass()]


class BlockDefinition(BaseBlock):

    def __init__(self, name, qname, attributes):
        super(BlockDefinition, self).__init__(name, qname, attributes)
        self.block_name = attributes['s']
        self.type = attributes['type']
        self.category = attributes['category']
        self.inner_functions = []
        self.local_variables = []

    def to_ast(self, ctx):
        ctx = ctx.copy()
        ctx.function = self
        name = self.function_name
        args = ast.arguments([ast.Name(arg, ast.Param())
                              for arg in self.function_arguments],
                             None, None, [])
        script = self.find_child(['script'])
        script_ast = script.to_ast(ctx)
        vars = [ast.Global(['_globals']),
                ast.Assign([ast.Name('_locals', ast.Store())],
                           ast.Dict([], []))]

        if script.has_body():
            # Put any inner functions at the start of the body.  This has
            # to happen after the body has been evaluated.
            body = vars + self.inner_functions + script_ast
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

    def is_argument(self, name):
        if name in self.function_arguments:
            return True
        return False

    def is_local_variable(self, name):
        if name in self.local_variables:
            return True
        return False


class CustomBlock(BaseBlock):
    counter = itertools.count().next

    def __init__(self, name, qname, attributes):
        super(CustomBlock, self).__init__(name, qname, attributes)
        self.block_name = attributes['s']

    def to_func(self, ctx, func, body):
        """Append the custom block as a function into the parent functions
        scope."""
        func_name = 'custom_block_' + str(self.counter())
        args = ast.arguments([ast.Name(arg, ast.Param())
                              for arg in func.function_arguments],
                             None, None, [])
        fn = ast.FunctionDef(func_name, args, body, [])
        ctx.body.append(fn)
        return func_name

    def to_ast(self, ctx):
        func = ctx.lookupCustomBlock(self.block_name)
        args = []
        for arg, type in zip(self.children, func.function_argument_types):
            if isinstance(arg, Script):
                ctx1 = ctx.copy()
                ctx1.function = func
                ctx1.variables.extend(ctx.function.local_variables)
                ctx1.inherited_scope.extend(ctx.function.function_arguments)
                arg_ast = arg.to_ast(ctx1)
            else:
                arg_ast = arg.to_ast(ctx)
            if type == '%cs':
                name = self.to_func(ctx, func, arg_ast)
                args.append(ast.Name(name, ast.Load()))
            elif type == '%upvar':
                args.append(ast.Num(0))
            else:
                args.append(arg_ast)
        return ast.Call(ast.Name(func.function_name, ast.Load()),
                        args, [], None, None)


def block_handler(name, qname, attributes):
    # Handle expressions
    fn = attributes.get('s')
    if fn:
        block = builtin_blocks.get(fn, NotImplementedBlock)
        block_parser = block(name, qname, attributes)
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
    'list': List,
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
    # 'reportModulus': reportModulus,
    # 'reportRound': reportRound,  # rounded
    # 'reportMonadic': reportMonadic,  # computeFunction:of:
    # 'reportIsA': reportIsA,  # isObject:type:
    'reportCAR': reportCAR,
    'reportCDR': reportCDR,
    'reportCONS': reportCONS,

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
    'reportListItem': reportListItem,
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


class Context(object):
    def __init__(self, custom_blocks=None, function=None, module=None,
                 used_custom_blocks=None, variables=[], inherited_scope=[],
                 body=None):
        self.custom_blocks = custom_blocks
        self.function = function
        self.module = module
        self.variables = list(variables)
        self.inherited_scope = list(inherited_scope)
        self.body = None
        self.used_custom_blocks = used_custom_blocks

    def lookupCustomBlock(self, name):
        if name not in self.used_custom_blocks:
            self.used_custom_blocks.append(name)
        if name not in self.custom_blocks:
            raise Exception("Block '%s' not found in: %s"
                            % (name, self.custom_blocks.keys()))
        return self.custom_blocks[name]

    def copy(self):
        kwargs = vars(self).copy()
        return Context(**kwargs)

    def popBody(self):
        body = self.body
        self.body = None
        return body

    def is_local_variable(self, name):
        if name in self.variables:
            return True
        if self.function and self.function.is_local_variable(name):
            return True
        return False

    def is_argument(self, name):
        if name in self.inherited_scope:
            return True
        if self.function and self.function.is_argument(name):
            return True
        return False


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
        globals = ast.Global(['_globals'])
        vars = ast.Assign([ast.Name('_globals', ast.Store())],
                          ast.Dict([], []))
        self._scripts = []
        for script in scripts.children:
            self._scripts.append(
                ast.FunctionDef('main_' + str(counter()),
                                args,
                                [globals, vars] + script.to_ast(ctx),
                                []))

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
        while True:
            try:
                block = ctx.used_custom_blocks.pop()
            except IndexError:
                break
            block = self.custom_blocks[block]
            try:
                block_ast = block.to_ast(ctx)
            except Exception:
                LOG.debug("Failed to generate function for %s"
                          % block.block_name)
                raise
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
