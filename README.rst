Snappy
======

Snap! server side execution in Python.


Installation
------------

Getting the code::

   git clone https://github.com/russell/snappy
   cd snappy
   pip install -e .
 
Running the server::

   twistd -ny snappy/webserver.tac


How it works?
-------------


Post a Snap! project XML to the server to execute it::

   $ curl -d @snappy/tests/sample_programs/wh_words.xml http://localhost:8888/jobs
   {"id": "88b78226-ea0b-11e3-bd62-040ccee11b9a"}

This returns the UUID for the job.

The state of this job can be queried using::

  $ curl http://localhost:8888/jobs/88b78226-ea0b-11e3-bd62-040ccee11b9a
  {"started": "2014-06-02T14:26:15.183880", "state": "finished", "finished": "2014-06-02T14:26:15.207053"}%
