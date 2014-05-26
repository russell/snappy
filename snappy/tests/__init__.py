from xml.sax.handler import ContentHandler

import codegen
from StringIO import StringIO
import lxml

from snappy import parser as snap_parser


class BlockParser():
    parser = None
    xml = ''

    def test_parse(self):
        parser = snap_parser.BlockParser()
        block_parser = snap_parser.Script(parser)
        parser.pushParser(block_parser)
        tree = lxml.etree.parse(StringIO(self.xml))
        lxml.sax.saxify(tree, parser)
        self.assertEqual([codegen.to_source(a) for a in block_parser.to_ast()],
                         [self.code])
        self.assertTrue(len(parser.parser_stack) == 1, parser.parser_stack)
        self.assertTrue(isinstance(block_parser.exprs[0], self.parser),
                        repr(block_parser.exprs[0]))
