import os
from os import path
import unittest
from snappy import tests
from snappy import parser


SAMPLE_PROGRAMS = path.join(path.dirname(__file__), 'sample_programs')


class TestreportTrue(tests.BlockParser, unittest.TestCase):
    parser = parser.reportTrue

    xml = """
    <block s="reportTrue"/>
    """

    code = 'True'


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
    Pass"""


class TestBlockParser(unittest.TestCase):

    def setUp(self):
        super(TestBlockParser, self).setUp()

    def test_if_else(self):
        filename = path.join(SAMPLE_PROGRAMS, 'wh_words.xml')
        p = parser.parse(filename)
