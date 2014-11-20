import keyring
from pygit2 import Repository
from jira.client import JIRA

from .harvest import HarvestPlatform
from .utils import cached_property


class Lancet:
    def __init__(self, config):
        self.config = config

    @cached_property
    def repo(self):
        return Repository('./.git')

    def get_issue(self, key):
        # TODO: Move this method to the JIRA class
        if key.isdigit():
            project_key = self.config.get('tracker', 'default_project')
            if project_key:
                key = '{}-{}'.format(project_key, key)
        return self.tracker.issue(key)

    @cached_property
    def tracker(self):
        url = self.config.get('tracker', 'url')
        username = self.config.get('tracker', 'username')
        password = keyring.get_password('lancet+{}'.format(url), username)
        return JIRA(server=url, basic_auth=(username, password))

    @cached_property
    def timer(self):
        url = self.config.get('harvest', 'url')
        username = self.config.get('harvest', 'username')
        password = keyring.get_password('harvest+{}'.format(url), username)
        project_id = self.config.get('harvest', 'project_id')
        task_id = self.config.get('harvest', 'task_id')
        return HarvestPlatform(server=url, basic_auth=(username, password),
                               project_id=project_id, task_id=task_id)
