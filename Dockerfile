FROM python:2.7-alpine
ADD . /rancher-gitlab-deployment
WORKDIR /rancher-gitlab-deployment
RUN python /rancher-gitlab-deployment/setup.py install
RUN ln -s /usr/local/bin/rancher-gitlab-deploy /usr/local/bin/deploy
CMD rancher-gitlab-deploy
