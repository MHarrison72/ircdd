from twisted.cred import portal, checkers
from twisted.words import service

userdata = {
    'user': 'password'
    }


def makeContext(config):
    ctx = dict(config)

    # TODO: Initialize DB driver
    # ctx.rethinkdb =
    # TODO: Initialize NSQ driver
    # ctx.nsq =

    # TODO: Make a custom realm that integrates with the database?
    ctx['realm'] = service.InMemoryWordsRealm('placeholder_realm')
    ctx['realm'].addGroup(service.Group('placeholder_group'))

    # TODO: Make a custom checker & portal that integrate with the database?
    placeholder_db = checkers.InMemoryUsernamePasswordDatabaseDontUse(**userdata)
    ctx['portal'] = portal.Portal(ctx['realm'], [placeholder_db])

    return ctx
