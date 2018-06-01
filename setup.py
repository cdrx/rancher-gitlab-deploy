from setuptools import setup

setup(name='rancher-gitlab-deploy',
    version='1.5',
    description='Command line tool to ease updating services in Rancher from your GitLab CI pipeline',
    url='https://github.com/cdrx/rancher-gitlab-deploy',
    author='cdrx',
    license='MIT',
    packages=[
        'rancher_gitlab_deploy_upgrade',
        'rancher_gitlab_deploy_finish_upgrade',
        'rancher_gitlab_deploy_rollback'
    ],
    zip_safe=False,
    install_requires=[
        'click',
        'requests',
        'colorama'
    ],
    entry_points = {
        'console_scripts': [
            'rancher-gitlab-deploy-upgrade=rancher_gitlab_deploy_upgrade.cli:main',
            'rancher-gitlab-deploy-finish-upgrade=rancher_gitlab_deploy_finish_upgrade.cli:main',
            'rancher-gitlab-deploy-rollback=rancher_gitlab_deploy_rollback.cli:main'
        ],
    }
)
