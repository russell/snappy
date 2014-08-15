import datetime
import json
import os
import sys
import uuid

from twisted.internet import reactor, defer, protocol
from twisted.python import log
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
import astor

from snappy import parser

JOB_DIR = 'jobs/'


def generate_job_id():
    while True:
        id = uuid.uuid1()
        if id in os.listdir(JOB_DIR):
            continue
        return str(id)


def parse_datetime(dt_str):
    dt, _, us = dt_str.partition(".")
    dt = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    us = int(us.rstrip("Z"), 10)
    return dt + datetime.timedelta(microseconds=us)


class NoResource(Resource):

    def render_GET(self, request):
        request.setHeader("Access-Control-Allow-Origin", "*")
        request.setHeader("content-type", "application/json")
        request.setResponseCode(404)
        return json.dumps({'error': "Resource Not Found."})


class JSONFileResource(Resource):

    def __init__(self, filename):
        self.filename = filename

    def render_GET(self, request):
        request.setHeader("Access-Control-Allow-Origin", "*")
        request.setHeader("content-type", "application/json")
        if not os.path.exists(self.filename):
            return NoResource()
        return json.dumps(json.load(open(self.filename)))


class FileResource(Resource):

    def __init__(self, filename):
        self.filename = filename

    def render_GET(self, request):
        request.setHeader("Access-Control-Allow-Origin", "*")
        request.setHeader("content-type", "text/plain")
        if not os.path.exists(self.filename):
            return NoResource()
        return open(self.filename).read()


class JobProcess(protocol.ProcessProtocol):

    def __init__(self, job_handler, id):
        self.id = id
        self.job_handler = job_handler
        self.data = ""
        self.logfile = open(job_handler.log_file, 'w')
        self.deferreds = []

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
        for d in self.deferreds:
            d.callback(self)

    def wait_for(self):
        d = defer.Deferred()
        self.deferreds.append(d)
        return d


class JobHandler(Resource):

    def __init__(self, handler, id, body=None):
        Resource.__init__(self)
        self.state = 'finished'
        self.started = None
        self.finished = None
        self.handler = handler
        self.id = id
        self.job_dir = os.path.join(JOB_DIR, id)
        self.job_process = None
        self.result_file = os.path.join(self.job_dir, 'result.json')
        self.log_file = os.path.join(self.job_dir, 'job.log')
        self.state_file = os.path.join(self.job_dir, 'job.state')
        if body:
            self.state = 'stopped'
            self.startJob(body)
        if os.path.exists(self.state_file):
            state = json.load(open(self.state_file))
            self.started = parse_datetime(state['started'])
            self.finished = parse_datetime(state['finished'])
            self.state = state['state']

    def getChild(self, name, request):
        if name == 'result':
            return JSONFileResource(self.result_file)
        if name == 'log':
            return FileResource(self.log_file)
        return NoResource()

    def startJob(self, body):
        os.mkdir(self.job_dir)
        project = json.loads(body)

        # sprit_id = project['sprite_idx']
        block_id = project['block_idx']

        # Write uploaded program
        xml = os.path.join(self.job_dir, 'job.xml')
        with open(xml, 'w') as file:
            file.write(project['project'].encode('utf-8'))

        # Parse and write python program
        p = parser.parses(project['project'].encode('utf-8'))
        ctx = p.create_context()
        file_ast = p.to_ast(ctx, 'main_%s' % block_id)
        code = astor.to_source(file_ast)
        program = os.path.join(self.job_dir, 'job.py')
        with open(program, 'w') as file:
            file.write(code)
        self.job_process = JobProcess(self, self.id)
        reactor.spawnProcess(
            self.job_process, sys.executable,
            [sys.executable, program], env=os.environ)

    def processState(self, state):
        self.state = state
        self.started = datetime.datetime.now()

    def processExited(self, state):
        log.msg('Job Finished %s' % self.id)
        self.state = state
        self.finished = datetime.datetime.now()
        # Write process state
        state = self.state_dict()
        del state['result']
        open(self.state_file, 'w').write(json.dumps(state))
        self.handler.unregisterJob(self)

    def state_dict(self):
        state = {'state': self.state,
                 'id': self.id,
                 'started': (self.started.isoformat()
                             if self.finished else None),
                 'finished': (self.finished.isoformat()
                              if self.finished else None)}
        if os.path.exists(self.result_file):
            result = json.load(open(self.result_file))
            state['result'] = result
        return state

    def render_GET(self, request):
        request.setHeader("Access-Control-Allow-Origin", "*")
        request.setHeader("content-type", "application/json")
        if self.state == 'finished':
            return json.dumps(self.state_dict())
        d = self.job_process.wait_for()

        def return_state(result):
            request.write(json.dumps(self.state_dict()))
            request.finish()
        d.addCallback(return_state)
        return NOT_DONE_YET


class JobsHandler(Resource):

    def getChild(self, name, request):
        if name in os.listdir(JOB_DIR):
            return JobHandler(self, name)
        return NoResource()

    def render_GET(self, request):
        request.setHeader("Access-Control-Allow-Origin", "*")
        request.setHeader("content-type", "application/json")
        return json.dumps({'jobs': {'running': len(self.children),
                                    'completed': len(os.listdir(JOB_DIR))}})

    def render_POST(self, request):
        request.setHeader("Access-Control-Allow-Origin", "*")
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
        if not os.path.exists(JOB_DIR):
            os.mkdir(JOB_DIR)
