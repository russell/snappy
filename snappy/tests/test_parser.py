from os import path
import unittest

from snappy import tests
from snappy import parser


SAMPLE_PROGRAMS = path.join(path.dirname(__file__), 'sample_programs')


class TestdoSetVarParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doSetVar

    script = """
    <block s="doSetVar">
      <l>i</l>
      <l>hello</l>
    </block>
    """

    vars = {'i': 'hello'}


class TestdoSetVarIntParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doSetVar

    script = """
    <block s="doSetVar">
      <l>i</l>
      <l>4</l>
    </block>
    """
    vars = {'i': 4}


class TestdoSetVarListParser(tests.BlockParser, unittest.TestCase):
    parser = parser.doSetVar

    script = """
    <block s="doSetVar">
      <l>result</l>
      <block s="reportNewList">
        <list/>
      </block>
    </block>
    """

    report = {'result': []}


class TestdoChangeVar(tests.BlockParser, unittest.TestCase):
    parser = parser.doChangeVar

    script = """
    <block s="doSetVar">
      <l>i</l>
      <l>4</l>
    </block>
    <block s="doChangeVar">
      <l>i</l>
      <l>6</l>
    </block>
    """

    vars = {'i': 10}


class TestreportTrue(tests.BlockParser, unittest.TestCase):
    parser = parser.reportTrue

    script = """
    <block s="reportTrue"/>
    """

    report = {'result': True}


class TestreportNot(tests.BlockParser, unittest.TestCase):
    parser = parser.reportNot

    script = """
    <block s="reportNot">
      <block s="reportTrue"/>
    </block>
    """

    report = {'result': False}


class TestreportNewList(tests.BlockParser, unittest.TestCase):
    parser = parser.reportNewList

    script = """
    <block s="reportNewList">
      <list>
        <l>a</l>
        <l>b</l>
        <l>10</l>
      </list>
    </block>
    """

    report = {'result': ['a', 'b', 10]}


class TestreportAnd(tests.BlockParser, unittest.TestCase):
    parser = parser.reportAnd

    script = """
    <block s="reportAnd">
      <block s="reportNot">
        <block s="reportTrue"/>
      </block>
      <block s="reportTrue"/>
    </block>
    """

    report = {'result': False}


class TestreportEquals(tests.BlockParser, unittest.TestCase):
    parser = parser.reportEquals

    script = """
    <block s="reportEquals">
      <l>1</l>
      <l>2</l>
    </block>
    """

    report = {'result': False}


class TestreportLetter(tests.BlockParser, unittest.TestCase):
    parser = parser.reportListItem

    script = """
    <block s="reportLetter">
      <l>1</l>
      <l>word</l>
    </block>
    """

    report = {'result': 'w'}


class TestdoInsertInList(tests.BlockParser, unittest.TestCase):
    parser = parser.doInsertInList

    script = """
    <block s="doDeclareVariables">
      <list>
        <l>i</l>
      </list>
    </block>
    <block s="doSetVar">
      <l>i</l>
      <block s="reportNewList">
        <list>
          <l>10</l>
        </list>
      </block>
    </block>
    <block s="doInsertInList">
      <l>word</l>
      <l>
        <option>last</option>
      </l>
      <block var="i"/>
    </block>
    """

    report = {'result': [10, 'word']}


class TestdoInsertInList1(tests.BlockParser, unittest.TestCase):
    parser = parser.doInsertInList

    script = """
    <block s="doDeclareVariables">
      <list>
        <l>i</l>
      </list>
    </block>
    <block s="doSetVar">
      <l>i</l>
      <block s="reportNewList">
        <list>
          <l>10</l>
        </list>
      </block>
    </block>
    <block s="doInsertInList">
      <l>word</l>
      <l>
        <option>1</option>
      </l>
      <block var="i"/>
    </block>
    """

    report = {'result': ['word', 10]}


class TestdoInsertInListAny(tests.BlockParser, unittest.TestCase):
    parser = parser.doInsertInList

    script = """
    <block s="doDeclareVariables">
      <list>
        <l>i</l>
      </list>
    </block>
    <block s="doSetVar">
      <l>i</l>
      <block s="reportNewList">
        <list>
          <l>10</l>
        </list>
      </block>
    </block>
    <block s="doInsertInList">
      <l>word</l>
      <l>
        <option>any</option>
      </l>
      <block var="i"/>
    </block>
    """

    report = {'result': [10, 'word']}


class TestdoAddToList(tests.BlockParser, unittest.TestCase):
    parser = parser.doAddToList

    script = """
    <block s="doDeclareVariables">
      <list>
        <l>i</l>
      </list>
    </block>
    <block s="doSetVar">
      <l>i</l>
      <block s="reportNewList">
        <list>
          <l>10</l>
        </list>
      </block>
    </block>
    <block s="doAddToList">
      <l>this word</l>
      <block var="i"/>
    </block>
    """

    report = {'result': [10, 'this word']}


class TestdoIf(tests.BlockParser, unittest.TestCase):
    parser = parser.doIf

    script = """
    <block s="doIf">
      <block s="reportTrue"/>
      <script>
        <block s="doSetVar">
          <l>test</l>
          <l>true</l>
        </block>
      </script>
    </block>
    """
    vars = {'test': 'true'}


class TestdoIfPass(tests.BlockParser, unittest.TestCase):
    parser = parser.doIf

    script = """
     <block s="doIf">
       <block s="reportTrue"/>
       <script/>
     </block>
     <block s="doSetVar">
       <l>test</l>
       <l>true</l>
    </block>
    """

    vars = {'test': 'true'}


class TestdoForEach(tests.BlockParser, unittest.TestCase):
    parser = parser.doForEach

    script = """
    <block s="doDeclareVariables">
      <list>
        <l>i</l>
        <l>words</l>
      </list>
    </block>
    <block s="doSetVar">
      <l>words</l>
      <block s="reportNewList">
        <list>
          <l>a</l>
          <l>b</l>
          <l>10</l>
        </list>
      </block>
    </block>
    <block s="doSetVar">
      <l>i</l>
      <l>0</l>
    </block>
    <block s="doForEach">
      <l>word</l>
      <block var="words"/>
      <script>
        <block s="doChangeVar">
          <l>i</l>
          <l>1</l>
        </block>
      </script>
    </block>
    <block s="doReport">
      <block var="i"/>
    </block>
    """

    report = {'result': 3}


class TestBlockDefinition(tests.BlockParser, unittest.TestCase):
    parser = parser.BlockDefinition

    block = """
    <block-definition s="print %'data'" type="reporter" category="operators">
      <header/>
      <code/>
      <inputs>
        <input type="%s"/>
      </inputs>
      <script>
        <block s="doReport">
          <block var="data"/>
        </block>
      </script>
    </block-definition>
    """

    script = """
    <custom-block s="print %s">
      <l>Hello World</l>
    </custom-block>
    """

    report = {'result': 'Hello World'}

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


class TestArgumentParser(unittest.TestCase):
    pass


class TestWHWordsFunction(tests.BlockParser, unittest.TestCase):
    xml = open(path.join(SAMPLE_PROGRAMS, 'wh_words.xml')).read()

    report = {'result': [u'whoever', u'Who', u'What.', u'What']}


class TestReverseBlock(tests.BlockParser, unittest.TestCase):
    xml = open(path.join(SAMPLE_PROGRAMS, 'base_blocks.xml')).read()

    script = """
    <custom-block s="reverse %l">
      <block s="reportNewList">
        <list>
          <l>!</l>
          <l>World</l>
          <l>Hello</l>
        </list>
      </block>
    </custom-block>
    """

    report = {'result': ['Hello', 'World', '!']}
