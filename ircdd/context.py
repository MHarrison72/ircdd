from time import ctime
import yaml

from twisted import copyright
from twisted.cred import portal
from twisted.words import service

from ircdd import server
from ircdd.remote import RemoteReadWriter
from ircdd import database


class ConfigStore(dict):
    """
    Container for configuration values and shared acces modules.
    """
    data = {'hostname': 'localhost',
            'port': '5799',
            'nsqd_tcp_addresses': ['127.0.0.1:4150'],
            'lookupd_http_addresses': ['127.0.0.1:4161'],
            }

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, item):
        self.data[key] = item


def makeContext(config):
    """
    Constructs an initialized context from the config values.
    Returns:
        A dict mapping keys to available resources,
        including the original config values.
    """

    ctx = ConfigStore()

    # if user specified a configuration file
    # overwrite defaults with values from file
    if config.get('config') is not None:
        stream = file(config.get('config'), 'r')
        del config['config']
        # yaml.load turns a file into an object/dictionary
        conFile = yaml.load(stream)
        stream.close()
        for x in conFile:
            ctx[x] = conFile.get(x)

    # if user specified any values via command line
    # overwrite existing values
    for x in config:
        ctx[x] = config.get(x)

    # TODO: Initialize DB driver
    # ctx['rethinkdb'] =

    # TODO: Make a custom realm that integrates with the database?
    ctx['realm'] = service.InMemoryWordsRealm(ctx['hostname'])

    # TODO: Make a custom checker & portal that integrate with the database?
    mock_db = server.DatabaseCredentialsChecker()
    ctx['portal'] = portal.Portal(ctx['realm'], [mock_db])

    db = database.IRCDDatabase()
    db.initializeDB()
    db.addUser('kzvezdarov', 'kzvezdarov@gmail.com', 'password', True, '')
    db.addUser('mcginnisdan', 'mcginnis.dan@gmail.com', 'password', True, '')
    db.addUser('roman215', 'Roman215@comcast.net', 'password', True, '')
    db.addUser('mikeharrison', 'tud04305@temple.edu', 'password', True, '')
    db.addUser('kevinrothenberger', 'tud14472@temple.edu',
               'password', True, '')
    db.addChannel('#ircdd', 'kzvezdarov', 'private')
    channels = db.getChannelNames()
    for channel in channels:
        ctx['realm'].addGroup(service.Group(channel))
    ctx['server_info'] = dict(
        serviceName=ctx['realm'].name,
        serviceVersion=copyright.version,
        creationDate=ctime()
        )

    ctx['remote_rw'] = RemoteReadWriter(ctx['nsqd_tcp_addresses'],
                                        ctx['lookupd_http_addresses'],
                                        ctx['hostname'])

    return ctx
