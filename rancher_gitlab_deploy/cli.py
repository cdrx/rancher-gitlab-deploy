#!/usr/bin/python
import os, sys, subprocess
import click
import requests
import json
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
              help="The name of the service in Rancher to upgrade (defaults to the name of the service in GitLab)")
@click.option('--start-before-stopping/--no-start-before-stopping', default=True,
              help="Should Rancher start new containers before stopping the old ones?")
@click.option('--batch-size', default=1,
              help="Number of containers to upgrade at once")
@click.option('--batch-interval', default=2,
              help="Number of seconds to wait between upgrade batches")
@click.option('--upgrade-timeout', default=5*60,
              help="How long to wait, in seconds, for the upgrade to finish before exiting. To skip the wait, pass the --no-wait-for-upgrade-to-finish option.")
@click.option('--wait-for-upgrade-to-finish/--no-wait-for-upgrade-to-finish', default=True,
              help="Wait for Rancher to finish the upgrade before this tool exits")
@click.option('--new-image', default=None,
              help="If specified, replace the image (and :tag) with this one during the upgrade")
@click.option('--finish-upgrade/--no-finish-upgrade', default=True,
              help="Mark the upgrade as finished after it completes")
@click.option('--sidekicks/--no-sidekicks', default=False,
              help="Upgrade also service sidekicks")
def main(rancher_url, rancher_key, rancher_secret, environment, stack, service, new_image, batch_size, batch_interval, start_before_stopping, upgrade_timeout, wait_for_upgrade_to_finish, finish_upgrade, sidekicks):
    """Performs an in service upgrade of the service specified on the command line"""
    # split url to protocol and host
    if "://" not in rancher_url:
        bail("The Rancher URL doesn't look right")

    proto, host = rancher_url.split("://")
    api = "%s://%s:%s@%s/v1" % (proto, rancher_key, rancher_secret, host)

    # 1 -> Find the environment id in Rancher

    try:
        r = requests.get("%s/projects?limit=1000" % api)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to connect to Rancher at %s - is the URL and API key right?" % host)
    else:
        environments = r.json()['data']

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
        r = requests.get("%s/projects/%s/environments?limit=1000" % (
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
        bail("Unable to find a stack called '%s'. Does it exist in the '%s' environment?" % environment_name)

    # 3 -> Find the service in the stack

    try:
        r = requests.get("%s/projects/%s/environments/%s/services?limit=1000" % (
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

    # 4 -> Is the service elligible for upgrade?

    if service['state'] == 'upgraded':
        warn("The current service state is 'upgraded', marking the previous upgrade as finished before starting a new upgrade...")

        try:
            r = requests.post("%s/projects/%s/services/%s/?action=finishupgrade" % (
                api, environment_id, service['id']
            ))
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            bail("Unable to finish the previous upgrade in Rancher")

        attempts = 0
        while service['state'] != "active":
            sleep(2)
            attempts += 2
            if attempts > upgrade_timeout:
                bail("A timeout occured while waiting for Rancher to finish the previous upgrade")
            try:
                r = requests.get("%s/projects/%s/services/%s" % (
                    api, environment_id, service['id']
                ))
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                bail("Unable to request the service status from the Rancher API")
            else:
                service = r.json()

    if service['state'] != 'active':
        bail("Unable to start upgrade: current service state '%s', but it needs to be 'active'" % service['state'])

    msg("Upgrading %s/%s in environment %s..." % (stack['name'], service['name'], environment_name))

    upgrade = {'inServiceStrategy': {
        'batchSize': batch_size,
        'intervalMillis': batch_interval * 1000, # rancher expects miliseconds
        'startFirst': start_before_stopping,
        'launchConfig': {},
        'secondaryLaunchConfigs': []
    }}
    # copy over the existing config
    upgrade['inServiceStrategy']['launchConfig'] = service['launchConfig']

    if sidekicks:
        # copy over existing sidekicks config
        upgrade['inServiceStrategy']['secondaryLaunchConfigs'] = service['secondaryLaunchConfigs']

    if new_image:
        # place new image into config
        upgrade['inServiceStrategy']['launchConfig']['imageUuid'] = 'docker:%s' % new_image

    # 5 -> Start the upgrade

    try:
        r = requests.post("%s/projects/%s/services/%s/?action=upgrade" % (
            api, environment_id, service['id']
        ), json=upgrade)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        bail("Unable to request an upgrade on Rancher")

    # 6 -> Wait for the upgrade to finish

    if not wait_for_upgrade_to_finish:
        msg("Upgrade started")
    else:
        msg("Upgrade started, waiting for upgrade to complete...")
        attempts = 0
        while service['state'] != "upgraded":
            sleep(2)
            attempts += 2
            if attempts > upgrade_timeout:
                bail("A timeout occured while waiting for Rancher to complete the upgrade")
            try:
                r = requests.get("%s/projects/%s/services/%s" % (
                    api, environment_id, service['id']
                ))
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                bail("Unable to fetch the service status from the Rancher API")
            else:
                service = r.json()

        if not finish_upgrade:
            msg("Service upgraded")
            sys.exit(0)
        else:
            msg("Finishing upgrade...")
            try:
                r = requests.post("%s/projects/%s/services/%s/?action=finishupgrade" % (
                    api, environment_id, service['id']
                ))
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                bail("Unable to finish the upgrade in Rancher")

            attempts = 0
            while service['state'] != "active":
                sleep(2)
                attempts += 2
                if attempts > upgrade_timeout:
                    bail("A timeout occured while waiting for Rancher to finish the previous upgrade")
                try:
                    r = requests.get("%s/projects/%s/services/%s" % (
                        api, environment_id, service['id']
                    ))
                    r.raise_for_status()
                except requests.exceptions.HTTPError:
                    bail("Unable to request the service status from the Rancher API")
                else:
                    service = r.json()

            msg("Upgrade finished")

    sys.exit(0)

def msg(msg):
    click.echo(click.style(msg, fg='green'))

def warn(msg):
    click.echo(click.style(msg, fg='yellow'))

def bail(msg):
    click.echo(click.style('Error: ' + msg, fg='red'))
    sys.exit(1)
