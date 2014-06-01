from datetime import date
import uuid
import os
import sys
import json
import subprocess
from StringIO import StringIO
import datetime

import codegen
import cgi
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.python import log
from twisted.internet import protocol

from snappy import parser

JOB_DIR = 'jobs/'

def generate_job_id():
    while True:
        id = uuid.uuid1()
        if id in os.listdir(JOB_DIR):
            continue
        return str(id)


class NoResource(Resource):

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps({'error': "Resource Not Found."})


class JSONFileResource(Resource):

    def __init__(self, filename):
        self.filename = filename

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps(json.load(open(self.filename)))


class FileResource(Resource):

    def __init__(self, filename):
        self.filename = filename

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        return open(self.filename).read()


class JobProcess(protocol.ProcessProtocol):

    def __init__(self, job_handler, id):
        self.id = id
        self.job_handler = job_handler
        self.data = ""
        job_dir = os.path.join(JOB_DIR, str(id))
        logfilename = os.path.join(job_dir, 'job.out')
        self.logfile = open(logfilename, 'w')

    def connectionMade(self):
        log.msg('Started Job %s' % id)
        self.job_handler.processState('running')

    def outReceived(self, data):
        self.logfile.write(data)

    def errReceived(self, data):
        self.logfile.write(data)

    def processEnded(self, reason):
        if reason.value.exitCode == 0:
            self.job_handler.processExited('finished')
        else:
            self.job_handler.processExited('error')


class JobHandler(Resource):

    def __init__(self, handler, id, body=None):
        Resource.__init__(self)
        self.started = None
        self.finished = None
        self.handler = handler
        self.id = id
        self.job_dir = os.path.join(JOB_DIR, id)
        if body:
            self.state = 'stopped'
            self.startJob(body)
        else:
            self.state = 'finished'

    def getChild(self, name, request):
        if name == 'result':
            result = os.path.join(self.job_dir, 'result.json')
            if os.path.exists(result):
                return JSONFileResource(result)
        if name == 'log':
            log = os.path.join(self.job_dir, 'job.out')
            if os.path.exists(log):
                return FileResource(log)
        return NoResource()

    def startJob(self, body):
        os.mkdir(self.job_dir)

        # Write uploaded program
        xml = os.path.join(self.job_dir, 'job.xml')
        with open(xml, 'w') as file:
            file.write(body)

        # Parse and write python program
        p = parser.parses(body)
        ctx = p.create_context()
        file_ast = p.to_ast(ctx, 'main_0')
        code = codegen.to_source(file_ast)
        program = os.path.join(self.job_dir, 'job.py')
        with open(program, 'w') as file:
            file.write(code)
        job_process = JobProcess(self, self.id)
        reactor.spawnProcess(job_process,
                             'python', ['python', program],
                             env=os.environ)

    def processState(self, state):
        self.state = state
        self.started = datetime.datetime.now()

    def processExited(self, state):
        log.msg('Job Finished %s' % self.id)
        self.state = state
        self.finished = datetime.datetime.now()

        state_file = os.path.join(self.job_dir, 'job.state')
        log.msg(json.dumps(self.state_dict()))
        open(state_file, 'w').write(json.dumps(self.state_dict()))
        self.handler.unregisterJob(self)

    def state_dict(self):
        return {'state': self.state,
                'started': self.started.isoformat(),
                'finished': self.finished.isoformat()}

    def state_file(self):
        state_file = os.path.join(self.job_dir, 'job.state')
        return json.load(open(state_file))

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        if self.state == 'finished':
            return json.dumps(self.state_file())
        return json.dumps(self.state_dict())


class JobsHandler(Resource):

    def getChild(self, name, request):
        if name in os.listdir(JOB_DIR):
            return JobHandler(self, name)
        return NoResource()

    def render_GET(self, request):
        return json.dumps({'jobs': {'running': len(self.children),
                                    'completed': len(os.listdir(JOB_DIR))}})

    def render_POST(self, request):
        request.setHeader("content-type", "application/json")
        body = request.content.read()
        id = generate_job_id()
        self.children[id] = JobHandler(self, id, body)
        return json.dumps({'id': str(id)})

    def unregisterJob(self, job):
        if job.id in self.children:
            del self.children[job.id]


class SnappySite(Resource):
    def __init__(self):
        self.children = {
            'jobs': JobsHandler()
        }
