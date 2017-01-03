from setuptools import setup

setup(name='rancher-gitlab-deploy',
    version='1.2',
    description='Command line tool to ease updating services in Rancher from your GitLab CI pipeline',
    url='https://github.com/cdrx/rancher-gitlab-deploy',
    author='cdrx',
    license='MIT',
    packages=['rancher_gitlab_deploy'],
    zip_safe=False,
    install_requires=[
        'click',
        'requests',
        'colorama'
    ],
    entry_points = {
        'console_scripts': ['rancher-gitlab-deploy=rancher_gitlab_deploy.cli:main'],
    }
)
