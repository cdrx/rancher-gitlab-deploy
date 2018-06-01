FROM python:2.7-alpine
ADD . /rancher-gitlab-deploy
WORKDIR /rancher-gitlab-deploy
RUN python /rancher-gitlab-deploy/setup.py install
RUN ln -s /usr/local/bin/rancher-gitlab-deploy-upgrade /usr/local/bin/upgrade
RUN ln -s /usr/local/bin/rancher-gitlab-deploy-finish-upgrade /usr/local/bin/finish-upgrade
RUN ln -s /usr/local/bin/rancher-gitlab-deploy-rollback /usr/local/bin/rollback