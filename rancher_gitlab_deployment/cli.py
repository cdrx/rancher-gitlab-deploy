#!/usr/bin/python
import os, sys, subprocess
import click
import requests
import json
from time import sleep

@click.command()
@click.option('--url', prompt='Rancher server URL',
              help='The URL for your Rancher server, eg: http://rancher:8000')
@click.option('--key', prompt='API Key',
              help="The environment or account API key")
@click.option('--secret', prompt='API Secret',
              help="The secret for the access API key")
@click.option('--environment', default=None,
              help="The name of the environment to add the host into")
@click.option('--stack', default=None,
              help="The name of the stack in Rancher")
@click.option('--service', default=None,
              help="The name of the service in Rancher to upgrade")
def main(url, key, secret, environment, stack, service):
    """Performs an in service upgrade of the service specified on the command line"""
    # split url to protocol and host
    if "://" not in url:
        bail("The Rancher URL doesn't look right")

    proto, host = url.split("://")
    api = "%s://%s:%s@%s/v1" % (proto, key, secret, host)

    try:
        r = requests.get("%s/projects?limit=1000" % api)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Couldn't connect to Rancher at %s - is the URL and API key right?" % host)
    else:
        environments = r.json()['data']

    if environment is None:
        environment = environments[0]['id']
    else:
        for e in environments:
            if e['id'].lower() == environment.lower() or e['name'].lower() == environment.lower():
                environment = e['id']

    if not environment:
        bail("Couldn't match your request to an environment on Rancher")

    try:
        r = requests.get("%s/projects/%s/environments?limit=1000" % (
            api,
            environment
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        import traceback
        traceback.print_exc()
        bail("Couldn't fetch a list of stacks in the environment. Does your API key have the right permissions?")
    else:
        stacks = r.json()['data']

    for s in stacks:
        if s['name'] == stack.lower():
            stack = s['id']
            break
    else:
        bail("Couldn't find a stack called '%s', does it exist in Rancher? Is it in the --envirionment specified?" % stack)

    try:
        r = requests.get("%s/projects/%s/environments/%s/services?limit=1000" % (
            api,
            environment,
            stack
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Couldn't fetch a list of services in the stack. Does your API key have the right permissions?")
    else:
        services = r.json()['data']

    for s in services:
        if s['name'] == service.lower():
            service = s
            break
    else:
        bail("Couldn't find a service called '%s', does it exist in Rancher?" % stack)

    print environment
    print stack
    print service['id']

    upgrade = {'inServiceStrategy': {
        'batchSize': 1,
        'intervalMillis': 10000,
        'startFirst': True,
        'launchConfig': {},
        'secondaryLaunchConfigs': []
    }}

    if service['state'] == 'upgraded':
        bail("Mark the service as upgraded first")
        # post(HOST + URL_SERVICE + service_id + "?action=finishupgrade", "")
        # r = get(HOST + URL_SERVICE + service_id)
        # current_service_config = r.json()
        #
        # sleep_count = 0
        # while current_service_config['state'] != "active" and sleep_count < 60:
        #     print "Waiting for upgrade to finish..."
        #     time.sleep (2)
        #     r = get(HOST + URL_SERVICE + service_id)
        #     current_service_config = r.json()
        #     sleep_count += 1

    if service['state'] != 'active':
        bail("The service can not be upgraded as it's current status (%s) is not: active" % service['state'])

    # copy over the existing config
    upgrade['inServiceStrategy']['launchConfig'] = service['launchConfig']

    new_image = None
    if new_image != None:
        # place new image into config
        upgrade['inServiceStrategy']['launchConfig']['imageUuid'] = new_image
    print json.dumps(upgrade)
    try:
        r = requests.post("%s/projects/%s/services/%s/?action=upgrade" % (
            api,
            environment,
            service['id']
        ), upgrade)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        import traceback
        traceback.print_exc()
        bail("Couldn't request upgrade on Rancher")
    else:
        services = r.json()['data']

    try:
        r = requests.get("%s/projects/%s/services/%s" % (
            api,
            environment,
            service['id']
        ))
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Couldn't fetch a list of services in the stack. Does your API key have the right permissions?")
    else:
        service = r.json()

    print "Waiting for upgrade to finish..."
    sleep_count = 0
    while service['state'] != "upgraded" and sleep_count < 60:
        print "."
        time.sleep (2)
        r = requests.get("%s/projects/%s/services/%s" % (
            api,
            environment,
            service['id']
        ))
        service = r.json()
        sleep_count += 1

    print "Upgraded"

def msg(msg):
    click.echo(click.style(msg, fg='green'))

def bail(msg):
    click.echo(click.style('Error: ' + msg, fg='red'))
    sys.exit(1)
