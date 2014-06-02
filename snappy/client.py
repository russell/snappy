#!/usr/bin/python

import json
import logging

import requests


log = logging.getLogger(__file__)


def submit_program(url, program_source, sprite_idx, block_idx):
    data = json.dumps(
        {'sprite_idx': sprite_idx,
         'block_idx': block_idx,
         'project': program_source})
    return requests.post(url + 'jobs', data=data)


def get_result(url, uuid):
    return requests.get(url + 'jobs/%s' % uuid)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help="Increase verbosity (specify multiple times for more).")
    parser.add_argument(
        '--url', default='http://localhost:8888/',
        help="")
    parser.add_argument(
        '--sprite-idx', default=0,
        help="The index of the sprite to execute")
    parser.add_argument(
        '--block-idx', default=0,
        help="The index of the block to execute.")
    parser.add_argument(
        'filename',
        help="The file containing the project.")

    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    resp = submit_program(args.url, open(args.filename).read(),
                          args.sprite_idx, args.block_idx)
    uuid = resp.json()['id']
    resp = get_result(args.url, uuid)
    print resp.json()
