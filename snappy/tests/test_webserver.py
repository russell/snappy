from StringIO import StringIO
from datetime import datetime
from os import path
import json
import shutil
import tempfile

from twisted.internet.defer import Deferred
from twisted.trial import unittest
from twisted.web.test.test_web import DummyRequest

from snappy import webserver


SAMPLE_PROGRAMS = path.join(path.dirname(__file__), 'sample_programs')


def program_path(filename):
    return path.join(SAMPLE_PROGRAMS, filename)


def parse_date(string):
    return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S.%f")


class TestJobsHandler(unittest.TestCase):
    def setUp(self):
        self.jobs_dir = tempfile.mkdtemp('snappy')
        self.service = webserver.SnapServer(self.jobs_dir)
        self.addCleanup(self.deleteJobDir)

    def deleteJobDir(self):
        shutil.rmtree(self.jobs_dir)

    def testGET(self):
        handler = webserver.JobsHandler(self.service)
        request = DummyRequest([''])
        json_res = handler.render_GET(request)
        res = json.loads(json_res)
        self.assertTrue('jobs' in res, res)
        self.assertEqual(res['jobs']['running'], 0, res)
        self.assertEqual(res['jobs']['completed'], 0, res)

    def testPOST(self):
        handler = webserver.JobsHandler(self.service)
        request = DummyRequest([''])
        request.content = StringIO(json.dumps(
            {'sprite_idx': 0,
             'block_idx': 0,
             'project': open(program_path('wh_words.xml')).read()}))

        # Start a job
        json_res = handler.render_POST(request)
        res = json.loads(json_res)
        self.assertTrue(res['id'], res)

        # Check job handler has the correct job_id
        job_handler = handler.children[res['id']]
        self.assertEqual(res['id'], job_handler.id)
        self.assertEqual(job_handler.state, 'running')

        # Check job process handler has the correct job_id
        job_process = job_handler.job_process
        self.assertEqual(res['id'], job_process.id)

        # Check state dict
        state = job_handler.state_dict()
        self.assertEqual(state['finished'], None)
        self.assertTrue(isinstance(parse_date(state['started']), datetime),
                        state['started'])
        self.assertEqual(state['id'], res['id'])
        self.assertEqual(state['state'], 'running')

        request = DummyRequest([''])
        d = Deferred()

        def _check_response(data):
            data = job_handler.render_GET(request)
            state = json.loads(data)
            self.assertTrue(isinstance(parse_date(state['finished']),
                                       datetime),
                            state['finished'])
            self.assertTrue(isinstance(parse_date(state['started']),
                                       datetime),
                            state['started'])
            self.assertEqual(state['id'], res['id'])
            self.assertEqual(state['state'], 'finished')
            self.assertEqual(state['result'],
                             ["whoever", "Who", "What.", "What"])

        d1 = job_process.wait_for()
        d1.addCallback(_check_response)
        d1.chainDeferred(d)
        return d
