import os
from os import path
import unittest
from snappy import tests
from snappy import parser


SAMPLE_PROGRAMS = path.join(path.dirname(__file__), 'sample_programs')


class TestNamedBlock(tests.BlockParser, unittest.TestCase):
    parser = parser.NamedBlock

    xml = """
    <block var="hello"/>
    """

    code = 'hello'


class TestdoSetVarParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doSetVar

    xml = """
    <block s="doSetVar">
      <l>i</l>
      <l>hello</l>
    </block>
    """

    code = "i = 'hello'"


class TestdoSetVarIntParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doSetVar

    xml = """
    <block s="doSetVar">
      <l>i</l>
      <l>4</l>
    </block>
    """

    code = 'i = 4'


class TestdoSetVarListParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doSetVar

    xml = """
    <block s="doSetVar">
      <l>result</l>
      <block s="reportNewList">
        <list/>
      </block>
    </block>
    """

    code = 'result = []'


class TestreportTrue(tests.BlockParser, unittest.TestCase):
    parser = parser.reportTrue

    xml = """
    <block s="reportTrue"/>
    """

    code = 'True'


class TestreportNot(tests.BlockParser, unittest.TestCase):
    parser = parser.reportNot

    xml = """
    <block s="reportNot">
      <block s="reportTrue"/>
    </block>
    """

    code = '(not True)'


class TestreportNewList(tests.BlockParser, unittest.TestCase):
    parser = parser.reportNewList

    xml = """
    <block s="reportNewList">
      <list>
        <l>a</l>
        <l>b</l>
        <l>10</l>
      </list>
    </block>
    """

    code = "['a', 'b', 10]"


class TestreportAnd(tests.BlockParser, unittest.TestCase):
    parser = parser.reportAnd

    xml = """
    <block s="reportAnd">
      <block var="word1"/>
      <block var="word2"/>
    </block>
    """

    code = "(word1 and word2)"


class TestreportEquals(tests.BlockParser, unittest.TestCase):
    parser = parser.reportEquals

    xml = """
    <block s="reportEquals">
      <l>1</l>
      <l>2</l>
    </block>
    """

    code = "(1 == 2)"


class TestreportLetter(tests.BlockParser, unittest.TestCase):
    parser = parser.reportLetter

    xml = """
    <block s="reportLetter">
      <l>1</l>
      <block var="word"/>
    </block>
    """

    code = "word[1]"


class TestdoInsertInList(tests.BlockParser, unittest.TestCase):
    parser = parser.doInsertInList

    xml = """
    <block s="doInsertInList">
      <block var="word"/>
      <l>
        <option>last</option>
      </l>
      <block var="result"/>
    </block>
    """

    code = "result.append(word)"


class TestdoInsertInList1(tests.BlockParser, unittest.TestCase):
    parser = parser.doInsertInList

    xml = """
    <block s="doInsertInList">
      <block var="word"/>
      <l>
        <option>1</option>
      </l>
      <block var="result"/>
    </block>
    """

    code = "result.insert(0, word)"


class TestdoInsertInListAny(tests.BlockParser, unittest.TestCase):
    parser = parser.doInsertInList

    xml = """
    <block s="doInsertInList">
      <block var="word"/>
      <l>
        <option>any</option>
      </l>
      <block var="result"/>
    </block>
    """

    code = "result.append(word)"


class TestdoAddToList(tests.BlockParser, unittest.TestCase):
    parser = parser.doAddToList

    xml = """
    <block s="doAddToList">
      <block var="thisword"/>
      <block var="result"/>
    </block>
    """

    code = "result.append(thisword)"


class TestdoDeclareVariablesParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doDeclareVariables

    xml = """
    <block s="doDeclareVariables">
      <list>
        <l>mapone</l>
        <l>mapmany</l>
      </list>
    </block>
    """

    code = '(mapone, mapmany) = (None, None)'


class TestdoIf(tests.BlockParser, unittest.TestCase):
    parser = parser.doIf

    xml = """
    <block s="doIf">
      <block s="reportTrue"/>
      <script>
        <block s="doSetVar">
          <l>i</l>
          <l>0</l>
        </block>
      </script>
    </block>
    """

    code = """if True:
    i = 0"""


class TestdoIfPass(tests.BlockParser, unittest.TestCase):
    parser = parser.doIf

    xml = """
    <block s="doIf">
      <block s="reportTrue"/>
      <script/>
    </block>
    """

    code = """if True:
    pass"""


class TestdoForEach(tests.BlockParser, unittest.TestCase):
    parser = parser.doForEach

    xml = """
    <block s="doForEach">
      <l>word</l>
      <block var="words"/>
      <script>
      </script>
    </block>
    """

    code = """for word in words:
    pass"""


class TestBlockDefinition(tests.BlockParser, unittest.TestCase):
    parser = parser.BlockDefinition

    xml = """
    <block-definition s="empty? %&apos;data&apos;"
                      type="reporter" category="lists">
      <header/>
      <code/>
      <inputs>
        <input type="%l"/>
      </inputs>
      <script>
      </script>
      <password/>
      <salt/>
    </block-definition>
    """

    code = "def empty_data_(data):\n    pass"

    def test_arg_parsing(self):
        block = self.parser('block-definition', None,
                            {'s': 'foo',
                             'type': 'reporter',
                             'category': 'list'})
        self.assertEqual(block.function_name, 'foo')
        self.assertEqual(block.type, 'reporter')
        self.assertEqual(block.category, 'list')

        block = self.parser('block-definition', None,
                            {'s': "empty? %'data'",
                             'type': 'reporter',
                             'category': 'list'})
        self.assertEqual(block.function_name, 'empty_data_')
        self.assertEqual(block.type, 'reporter')
        self.assertEqual(block.category, 'list')
        self.assertEqual(block.function_arguments, ['data'])
class TestBlockParser(unittest.TestCase):

    def setUp(self):
        super(TestBlockParser, self).setUp()

    def test_wh_words(self):
        filename = path.join(SAMPLE_PROGRAMS, 'wh_words.xml')
        p = parser.parse(filename)
        self.assertTrue(len(p.scripts) == 2, p.scripts)
        self.assertTrue(len(p.custom_blocks) == 29, p.custom_blocks)
