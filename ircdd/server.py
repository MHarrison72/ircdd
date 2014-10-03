from twisted.words.service import IRCFactory
from twisted.application import internet


def makeServer(ctx):
    f = IRCFactory(ctx['realm'], ctx['portal'])

    irc_server = internet.TCPServer(ctx['port'], f)
    return irc_server
