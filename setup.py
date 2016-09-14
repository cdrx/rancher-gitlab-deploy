from setuptools import setup

setup(name='rancher-gitlab-deployment',
    version='1.0',
    description='Command line tool to ease updating services in Rancher from your GitLab CI pipeline',
    url='https://github.com/cdrx/rancher-gitlab-deployment',
    author='Chris Rose',
    license='MIT',
    packages=['rancher_gitlab_deployment'],
    zip_safe=False,
    install_requires=[
        'click',
        'requests',
        'colorama'
    ],
    entry_points = {
        'console_scripts': ['rancher-gitlab-deploy=rancher_gitlab_deployment.cli:main'],
    }
)
