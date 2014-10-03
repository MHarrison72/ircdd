from zope.interface import implements

from twisted.cred import credentials, strcred
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

import ircdd.server as ircdd_server
from ircdd import context


class Options(usage.Options, strcred.AuthOptionMixin):
    supportedInterfaces = (credentials.IUsernamePassword)
    optParameters = [
        ['host', 'h', 'localhost'],
        ['port', 'p', 5799],
        ]
    optFlags = [['ssl', 's'], ['verbose', 'v']]


class IRCDDServiceMaker():
    implements(IServiceMaker, IPlugin)
    tapname = 'ircdd'
    description = 'Distributed IRC Daemon'
    options = Options

    def makeService(self, config):
        ctx = context.makeContext(config)
        return ircdd_server.makeServer(ctx)

serviceMaker = IRCDDServiceMaker()
