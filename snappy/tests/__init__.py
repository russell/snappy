from StringIO import StringIO
from xml.sax.handler import ContentHandler
import lxml

import astor

from snappy import parser as snap_parser


class BlockParser():
    parser = None
    xml = ''

    def test_parse(self):
        parser = snap_parser.BlockParser()
        block_parser = snap_parser.Script(None, 'script', {})
        parser.pushT(block_parser)
        tree = lxml.etree.parse(StringIO(self.xml))
        lxml.sax.saxify(tree, parser)
        ctx = parser.create_context()
        self.assertEqual([astor.to_source(a)
                          for a in parser.children[0].to_ast(ctx)],
                         [self.code])
        # There will be a remainder while testing, due to the manually
        # created script tag.
        self.assertTrue(len(parser.stack) == 1, parser.stack)
        self.assertTrue(isinstance(block_parser.children[0], self.parser),
                        "Block isn't correct type, should be %s but is %s" % (
                            self.parser,
                            repr(block_parser.children[0].__class__)))
