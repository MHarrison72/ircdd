import rethinkdb as r

from twisted.test import proto_helpers
from twisted.words.protocols import irc

from ircdd.server import IRCDDFactory, ShardedUser, ShardedGroup
from ircdd.remote import _channels, _topics
from ircdd.remote import _delete_channel, _delete_topic
from ircdd.context import makeContext
from ircdd.tests import integration


class TestShardedUser:
    def setUp(self):
        self.conn = r.connect(db=integration.DB,
                              host=integration.HOST,
                              port=integration.PORT)

        integration.createTables()

        config = dict(nsqd_tcp_address=["127.0.0.1:4150"],
                      lookupd_http_address=["127.0.0.1:4161"],
                      hostname="testserver",
                      group_on_request=True,
                      user_on_request=True,
                      db=integration.DB,
                      rdb_host=integration.HOST,
                      rdb_port=integration.PORT
                      )
        self.ctx = makeContext(config)

        self.factory = IRCDDFactory(self.ctx)
        self.protocol = self.factory.buildProtocol(("127.0.0.1", 0))
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)

        self.shardedUser = ShardedUser(self.ctx, "john")
        self.shardedUser.mind = self.protocol
        self.shardedUser.mind.name = "john"

    def tearDown(self):
        self.shardedUser = None
        self.transport.loseConnection()
        self.protocol.connectionLost(None)

        integration.dropTables()

        self.conn.close()

        for topic in _topics(self.ctx["lookupd_http_address"]):
            for chan in _channels(topic, self.ctx["lookupd_http_address"]):
                _delete_channel(topic, chan, self.ctx["lookupd_http_address"])
            _delete_topic(topic, self.ctx["lookupd_http_address"])

        self.ctx["db"].conn.close()
        self.ctx = None

    def test_userHeartbeats(self):
        self.shardedUser.loggedIn(self.ctx.realm, None)

        hb = r.db(integration.DB).table("user_sessions").get(
            "john"
        ).run(self.conn)

        assert hb
        assert hb.get("last_heartbeat")
        assert hb.get("last_heartbeat") != ""

        self.ctx.db.heartbeatUserSession("john")
        hb2 = r.db(integration.DB).table("user_sessions").get(
            "john"
        ).run(self.conn)

        assert hb2
        assert hb2.get("last_heartbeat")
        assert hb2.get("last_heartbeat") != ""

        assert hb.get("last_heartbeat") != hb2.get("last_heartbeat")

    def test_userInGroupHeartbeats(self):
        group = ShardedGroup(self.ctx, "test_group")

        self.shardedUser.join(group)

        hb = r.db(integration.DB).table("group_states").get(
            "test_group"
        ).run(self.conn)

        assert hb
        assert hb["user_heartbeats"]["john"]
        assert hb["user_heartbeats"]["john"] != ""


class TestIRCDDAuth:
    def setUp(self):
        self.conn = r.connect(db=integration.DB,
                              host=integration.HOST,
                              port=integration.PORT)

        integration.createTables()

        config = dict(nsqd_tcp_address=["127.0.0.1:4150"],
                      lookupd_http_address=["127.0.0.1:4161"],
                      hostname="testserver",
                      group_on_request=True,
                      user_on_request=True,
                      db=integration.DB,
                      rdb_host=integration.HOST,
                      rdb_port=integration.PORT
                      )
        self.ctx = makeContext(config)

        self.ctx["db"].createUser("john", password="pw", registered=True)
        self.ctx["db"].createUser("jane", password="pw2", registered=True)
        self.ctx["db"].createUser("jill", password="pw3", registered=True)

        self.factory = IRCDDFactory(self.ctx)
        self.protocol = self.factory.buildProtocol(("127.0.0.1", 0))
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)

    def tearDown(self):
        self.transport.loseConnection()
        self.protocol.connectionLost(None)

        integration.dropTables()

        self.conn.close()

        for topic in _topics(self.ctx["lookupd_http_address"]):
            for chan in _channels(topic, self.ctx["lookupd_http_address"]):
                _delete_channel(topic, chan, self.ctx["lookupd_http_address"])
            _delete_topic(topic, self.ctx["lookupd_http_address"])

        self.ctx["db"].conn.close()
        self.ctx = None

    def getResponse(self):
        response = self.protocol.transport.value().splitlines()
        self.protocol.transport.clear()
        return map(irc.parsemsg, response)

    def test_anon_login(self):
        # Anonymous users still need to give the server a password
        # because of how Twisted's IRC works.
        self.protocol.irc_PASS("", ["password"])
        self.protocol.irc_NICK("", ["anonuser"])

        version = ("Your host is testserver, running version %s" %
                   (self.factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (self.factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["anonuser", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["anonuser", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["anonuser", "connected to Twisted IRC"]),
                    ("testserver", "002", ["anonuser", version]),
                    ("testserver", "003", ["anonuser", creation]),
                    ("testserver", "004",
                    ["anonuser", "testserver",
                     self.factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse()
        assert response == expected

    def test_registered_login(self):
        """
        Connecting to the server, sending /pass <pw>,
        then /nick <name> logs the registered user in.
        """

        self.protocol.irc_PASS("", ["pw"])
        self.protocol.irc_NICK("", ["john"])

        version = ("Your host is testserver, running version %s" %
                   (self.factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (self.factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["john", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["john", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["john", "connected to Twisted IRC"]),
                    ("testserver", "002", ["john", version]),
                    ("testserver", "003", ["john", creation]),
                    ("testserver", "004",
                    ["john", "testserver",
                     self.factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse()
        assert response == expected

    def test_anon_login_create_fail(self):
        self.ctx["realm"].createUserOnRequest = False

        self.protocol.irc_PASS("", ["password"])
        self.protocol.irc_NICK("", ["anonuser"])

        version = ("Your host is testserver, running version %s" %
                   (self.factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (self.factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["anonuser", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["anonuser", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["anonuser", "connected to Twisted IRC"]),
                    ("testserver", "002", ["anonuser", version]),
                    ("testserver", "003", ["anonuser", creation]),
                    ("testserver", "004",
                    ["anonuser", "testserver",
                     self.factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse()
        # Improve this to expect a specific error output
        assert response != expected

    def test_anon_login_nick_taken_fail(self):
        self.protocol.irc_PASS("", ["password"])
        self.protocol.irc_NICK("", ["anonuser"])

        version = ("Your host is testserver, running version %s" %
                   (self.factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (self.factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["anonuser", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["anonuser", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["anonuser", "connected to Twisted IRC"]),
                    ("testserver", "002", ["anonuser", version]),
                    ("testserver", "003", ["anonuser", creation]),
                    ("testserver", "004",
                    ["anonuser", "testserver",
                     self.factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse()
        assert response == expected
        self.protocol.irc_PASS("", ["password"])
        self.protocol.irc_NICK("", ["anonuser"])

        expected_fail = [('testserver', '375',
                         ['anonuser', '- testserver Message of the Day - ']),
                         ('testserver', '376',
                         ['anonuser', 'End of /MOTD command.']),
                         ('NickServ!NickServ@services', 'PRIVMSG',
                         ['anonuser',
                          'Already logged in.  No pod people allowed!'])]

        response_fail = self.getResponse()

        assert response_fail == expected_fail

    def test_registered_login_pw_fail(self):
        self.protocol.irc_PASS("", ["bad_password"])
        self.protocol.irc_NICK("", ["john"])

        expected = [('testserver', '375',
                    ['john', '- testserver Message of the Day - ']),
                    ('testserver', '376', ['john', 'End of /MOTD command.']),
                    ('NickServ!NickServ@services', 'PRIVMSG',
                    ['john', 'Login failed.  Goodbye.'])]

        response = self.getResponse()
        assert response == expected
