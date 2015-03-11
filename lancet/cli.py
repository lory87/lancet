import os
import sys
import pdb
import importlib
import shlex
import subprocess

import click
from click.utils import make_str

from . import __version__
from .settings import load_config, PROJECT_CONFIG
from .base import Lancet, WarnIntegrationHelper, ShellIntegrationHelper
from .utils import hr


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


class SubprocessExecuter(click.BaseCommand):
    def parse_args(self, ctx, args):
        ctx.args = args
        return args

    def invoke(self, ctx):
        ctx.exit(subprocess.call(ctx.args[0], shell=True))


class ConfigurableLoader(click.Group):

    @classmethod
    def get_config(cls):
        if os.path.exists(PROJECT_CONFIG):
            return load_config(PROJECT_CONFIG)
        else:
            return load_config()

    @classmethod
    def get_configured_commands(cls, config=None):
        if config is None:
            config = cls.get_config()
        return config.options('commands')

    @classmethod
    def get_configured_aliases(cls, config=None):
        if config is None:
            config = cls.get_config()
        return config.options('alias')

    @staticmethod
    def show_help_all(ctx, param, value):
        if value and not ctx.resilient_parsing:
            # Explicitly set the flag to show hidden subcommands, otherwise
            # the code in the `get_help` method would set it to False.
            ctx.show_hidden_subcommands = True
            click.echo(ctx.get_help())
            ctx.exit()

    def list_commands(self, ctx):
        commands = set(super().list_commands(ctx))
        commands = commands.union(self.get_configured_commands())

        # Do not list hidden subcommands if the flag is explicitly set on the
        # context. By default include all commands.
        if not getattr(ctx, 'show_hidden_subcommands', True):
            commands = [c for c in commands if not c.startswith('_')]
        return sorted(commands)

    def list_aliases(self, ctx):
        return sorted(self.get_configured_aliases())

    def get_help(self, ctx):
        # By default do not list hidden subcommands.
        ctx.show_hidden_subcommands = getattr(
            ctx, 'show_hidden_subcommands', False)
        return super().get_help(ctx)

    def format_options(self, ctx, formatter):
        super().format_options(ctx, formatter)
        self.format_aliases(ctx, formatter)

    def format_aliases(self, ctx, formatter):
        rows = []
        for alias in self.list_aliases(ctx):
            rows.append((alias, self.get_config().get('alias', alias)))

        if rows:
            with formatter.section('Aliases'):
                formatter.write_dl(rows)

    def resolve_command(self, ctx, args):
        cmd_name = make_str(args[0])

        if cmd_name in self.get_configured_aliases():
            if cmd_name in self.list_commands(ctx):
                # Shadowing of existing commands is explicitly disabled.
                click.secho('"{}" references an existing command. I am '
                            'ignoring the alias definition.'.format(cmd_name),
                            fg='yellow')
            else:
                # If the command references a configured alias, retrieve it
                # from the configuration.
                alias = self.get_config().get('alias', cmd_name)
                args = args[1:]
                if alias.startswith('!'):
                    cmd = SubprocessExecuter('')
                    additional_args = ' '.join(shlex.quote(a) for a in args)
                    return '', cmd, [alias[1:] + ' ' + additional_args]
                else:
                    args = shlex.split(alias) + args

        return super().resolve_command(ctx, args)

    def get_command(self, ctx, name):
        if name in self.get_configured_commands():
            path = self.get_config().get('commands', name)
            module_path, attr_name = path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, attr_name)
        else:
            return super().get_command(ctx, name)


@click.command(context_settings=CONTEXT_SETTINGS, cls=ConfigurableLoader)
@click.version_option(version=__version__, message='%(prog)s %(version)s')
@click.option('-d', '--debug/--no-debug', default=False,
              help=('Drop into the debugger if the command execution raises '
                    'an exception.'))
@click.option('--help-all', is_flag=True, is_eager=True, expose_value=False,
              callback=ConfigurableLoader.show_help_all,
              help='Show this message including hidden subcommands.')
@click.pass_context
def main(ctx, debug):
    # TODO: Enable this using a command line switch
    # import logging
    # logging.basicConfig(level=logging.DEBUG)

    if debug:
        def exception_handler(type, value, traceback):
            click.secho('\nAn exception occurred while executing the '
                        'requested command:', fg='red')
            hr(fg='red')
            sys.__excepthook__(type, value, traceback)

            click.secho('\nAs requested I will now drop you inside an '
                        'interactive debugging session:', fg='red')
            hr(fg='red')

            pdb.post_mortem(traceback)
        sys.excepthook = exception_handler

    try:
        integration_helper = ShellIntegrationHelper(
            os.environ['LANCET_SHELL_HELPER'])
    except KeyError:
        integration_helper = WarnIntegrationHelper()

    if os.path.exists(PROJECT_CONFIG):
        config = load_config(PROJECT_CONFIG)
    else:
        config = load_config()

    ctx.obj = Lancet(config, integration_helper)
    ctx.obj.call_on_close = ctx.call_on_close
    ctx.call_on_close(integration_helper.close)


@main.command()
def _setup_helper():
    """Print the shell integration code."""
    base = os.path.abspath(os.path.dirname(__file__))
    helper = os.path.join(base, 'helper.sh')
    with open(helper) as fh:
        click.echo(fh.read())


# TODO:
# * review
#     pull
#     ci-status
#     pep8
#     diff
#     mergeability (rebase is of the submitter responsibility)
# * merge
#     pull, merge, delete
# * issues
#     list all open/assigned issues (or by filter)
# * comment
#     adds a comment to the currently active issue
