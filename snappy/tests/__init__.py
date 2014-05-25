from xml.sax.handler import ContentHandler

from StringIO import StringIO
import lxml

from snappy import parser as snap_parser


class TestParser(ContentHandler):

    def __init__(self):
        self.parser_stack = [self]

    def setInitialParser(self, parser):
        self.parser = parser
        self.pushParser(parser)

    def pushParser(self, parser):
        self.parser_stack.append(parser)
        return parser

    def popParser(self):
        return self.parser_stack.pop()

    def getParser(self):
        for parser in reversed(self.parser_stack):
            if isinstance(parser, (str, tuple)):
                continue
            return parser
        return self

    def startElementNS(self, name, qname, attributes):
        qname = qname.replace('-', '_')
        snap_parser.enter(self.getParser(), qname)(name, qname, attributes)

    def endElementNS(self, name, qname):
        qname = qname.replace('-', '_')
        snap_parser.leave(self.getParser(), qname)()

    def characters(self, data):
        if self.getParser() != self:
            self.getParser().characters(data)

    def __str__(self):
        return self.parser.__str__()


class BlockParser():
    parser = None
    xml = ''

    def test_parse(self):
        parser = TestParser()
        block_parser = self.parser(parser)
        parser.setInitialParser(block_parser)
        tree = lxml.etree.parse(StringIO(self.xml))
        lxml.sax.saxify(tree, parser)
        self.assertEqual(str(parser), self.code)
