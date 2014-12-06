from time import ctime
import yaml

from twisted import copyright
from twisted.cred import portal

from ircdd.realm import ShardedRealm
from ircdd import cred
from ircdd.remote import RemoteReadWriter
from ircdd import database


class ConfigStore(dict):
    """
    Container for configuration values and shared acces modules.
    Behaves like a dictionary whose keys can be accessed like object
    attributes.
    """

    def __init__(self, *args, **kwargs):
        super(ConfigStore, self).__init__(*args, **kwargs)
        self.__dict__ = self


def makeContext(config):
    """
    Constructs an initialized context from the config values.
    Returns a dict mapping keys to available resources,
    including the original config values.
    """

    ctx = ConfigStore()

    # if user specified a configuration file
    # overwrite defaults with values from file
    if config.get('config') is not None:
        stream = open(config.get('config'), 'r')
        del config['config']
        # yaml.load turns a file into an object/dictionary
        conFile = yaml.load(stream)
        stream.close()
        for option in conFile:
            ctx[option] = conFile.get(option)

    # if user specified any values via command line
    # overwrite existing values
    for option in config:
        if not ctx.get(option, None):
            ctx[option] = config.get(option)
        elif (config.defaults.get(option)
              and config.get(option) != config.defaults.get(option)):
            ctx[option] = config.get(option)

    ctx['realm'] = ShardedRealm(ctx, ctx['hostname'])

    cred_checker = cred.DatabaseCredentialsChecker(ctx)
    ctx['portal'] = portal.Portal(ctx['realm'], [cred_checker])

    ctx["db"] = database.IRCDDatabase(db=ctx["db"],
                                      host=ctx['rdb_host'],
                                      port=ctx['rdb_port'])

    ctx['server_info'] = dict(
        serviceName=ctx['realm'].name,
        serviceVersion=copyright.version,
        creationDate=ctime()
        )

    ctx['remote_rw'] = RemoteReadWriter(ctx['nsqd_tcp_address'],
                                        ctx['lookupd_http_address'],
                                        ctx['hostname'])

    return ctx
