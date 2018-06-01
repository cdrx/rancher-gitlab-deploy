#!/usr/bin/env python
import os, sys, subprocess
import click
import requests
import json
import logging
import contextlib
try:
    from http.client import HTTPConnection # py3
except ImportError:
    from httplib import HTTPConnection # py2

from time import sleep

@click.command()
@click.option('--rancher-url', envvar='RANCHER_URL', required=True,
              help='The URL for your Rancher server, eg: http://rancher:8000')
@click.option('--rancher-key', envvar='RANCHER_ACCESS_KEY', required=True,
              help="The environment or account API key")
@click.option('--rancher-secret', envvar='RANCHER_SECRET_KEY', required=True,
              help="The secret for the access API key")
@click.option('--environment', default=None,
              help="The name of the environment to add the host into " + \
                   "(only needed if you are using an account API key instead of an environment API key)")
@click.option('--stack', envvar='CI_PROJECT_NAMESPACE', default=None, required=True,
              help="The name of the stack in Rancher (defaults to the name of the group in GitLab)")
@click.option('--service', envvar='CI_PROJECT_NAME', default=None, required=True,
              help="The name of the service in Rancher to rollback (defaults to the name of the service in GitLab)")
@click.option('--rollback-timeout', default=5*60,
              help="How long to wait, in seconds, for a rollback before exiting.")
@click.option('--debug/--no-debug', default=False,
              help="Enable HTTP Debugging")
@click.option('--ssl-verify/--no-ssl-verify', default=True,
              help="Disable certificate checks. Use this to allow connecting to a HTTPS Rancher server using an self-signed certificate")
def main(rancher_url, rancher_key, rancher_secret, environment, stack, service, rollback_timeout, debug, ssl_verify):
    """Rollback previous upgrade of the service"""

    if debug:
        debug_requests_on()

    # split url to protocol and host
    if "://" not in rancher_url:
        bail("The Rancher URL doesn't look right")

    proto, host = rancher_url.split("://")
    api = "%s://%s/v1" % (proto, host)
    stack = stack.replace('.', '-')
    service = service.replace('.', '-')

    session = requests.Session()

    # Set verify based on --ssl-verify/--no-ssl-verify option
    session.verify = ssl_verify

    # 0 -> Authenticate all future requests
    session.auth = (rancher_key, rancher_secret)

    # 1 -> Find the environment id in Rancher
    try:
        r = session.get("%s/projects?limit=1000" % api)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to connect to Rancher at %s - is the URL and API key right?" % host)
    else:
        environments = r.json()['data']

    environment_id = None
    if environment is None:
        environment_id = environments[0]['id']
        environment_name = environments[0]['name']
    else:
        for e in environments:
            if e['id'].lower() == environment.lower() or e['name'].lower() == environment.lower():
                environment_id = e['id']
                environment_name = e['name']

    if not environment_id:
        if environment:
            bail("The '%s' environment doesn't exist in Rancher, or your API credentials don't have access to it" % environment)
        else:
            bail("No environment in Rancher matches your request")

    # 2 -> Find the stack in the environment

    try:
        r = session.get("%s/projects/%s/environments?limit=1000" % (
            api,
            environment_id
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to fetch a list of stacks in the environment '%s'" % environment_name)
    else:
        stacks = r.json()['data']

    for s in stacks:

        if s['name'].lower() == stack.lower():
            stack = s
            break
    else:
        bail("Unable to find a stack called '%s'. Does it exist in the '%s' environment?" % (stack, environment_name))

    # 3 -> Find the service in the stack

    try:
        r = session.get("%s/projects/%s/environments/%s/services?limit=1000" % (
            api,
            environment_id,
            stack['id']
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to fetch a list of services in the stack. Does your API key have the right permissions?")
    else:
        services = r.json()['data']

    for s in services:
        if s['name'].lower() == service.lower():
            service = s
            break
    else:
        bail("Unable to find a service called '%s', does it exist in Rancher?" % service)

    # 4 -> Rollback the service

    if service['state'] != 'upgraded':
            bail("Unable to rollback: current service state '%s', but it needs to be 'upgraded'" % service['state'])

    try:
        r = session.post("%s/projects/%s/services/%s/?action=rollback" % (
            api, environment_id, service['id']
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to rollback")

    attempts = 0
    while service['state'] != "active":
        sleep(2)
        attempts += 2
        if attempts > rollback_timeout:
            bail("A timeout occured while waiting for Rancher to rollback the previous upgrade")
        try:
            r = session.get("%s/projects/%s/services/%s" % (
                api, environment_id, service['id']
            ))
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            bail("Unable to request the service status from the Rancher API")
        else:
            service = r.json()

    sys.exit(0)

def msg(msg):
    click.echo(click.style(msg, fg='green'))

def warn(msg):
    click.echo(click.style(msg, fg='yellow'))

def bail(msg):
    click.echo(click.style('Error: ' + msg, fg='red'))
    sys.exit(1)

def debug_requests_on():
    '''Switches on logging of the requests module.'''
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
