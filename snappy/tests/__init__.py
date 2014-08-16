import ast
import imp

import astor

from snappy import parser as snap_parser
from snappy import stdlib as snap_stdlib


class BlockParser():
    parser = None
    xml = """
<project name="wh_words" app="Snap! 4.0, http://snap.berkeley.edu" version="1">
  <stage name="Stage" width="480" height="360" costume="0"
         tempo="60" threadsafe="false" lines="round" codify="false"
         scheduled="false" id="1">
    <sprites>
      <sprite name="Graph" idx="1" x="0" y="0" heading="90" scale="1"
              rotation="1" draggable="false" costume="0" color="80,80,80"
              pen="tip" id="8">
        <costumes>
          <list id="9"/>
        </costumes>
        <sounds>
          <list id="10"/>
        </sounds>
        <variables/>
        <blocks/>
        <scripts>
          <script x="20" y="119">
{script}
          </script>
        </scripts>
        <nodeattrs/>
        <edgeattrs/>
      </sprite>
    </sprites>
  </stage>
  <blocks>
{block}
  </blocks>
</project>
"""

    block = ""
    blocks = []
    script = ""
    report = None
    vars = None

    def test_parse(self):
        snap_stdlib.cleanReport()
        if self.script:
            document = self.xml.format(
                script=self.script,
                block="".join(self.blocks) or self.block)
        else:
            document = self.xml
        parser = snap_parser.parses(document)
        ctx = parser.create_context()
        script = parser.to_ast(ctx)
        ast.fix_missing_locations(script)
        try:
            code = compile(script, '<string>', 'exec')
            module = imp.new_module(__name__ + '.compiled_block')

            exec code in module.__dict__
            module.main_0()

            if self.report:
                self.assertEqual(
                    module.stdlib._report, self.report,
                    "%s != %s\ncode::\n\n%s" % (module.stdlib._report,
                                                self.report,
                                                astor.to_source(script)))
            if self.vars:
                self.assertEqual(
                    module._globals, self.vars,
                    "%s != %s\ncode::\n\n%s" % (module._globals,
                                                self.vars,
                                                astor.to_source(script)))
        except:
            print "Generated AST object\n", ast.dump(script)
            parsed = ast.parse(astor.to_source(script))
            print "Parsed AST object\n", ast.dump(parsed)
            print "Script\n", astor.to_source(script)
            raise

        self.assertTrue(len(parser.stack) == 0, parser.stack)
