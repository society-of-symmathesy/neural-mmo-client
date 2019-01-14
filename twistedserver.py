from pdb import set_trace as T
import numpy as np

import sys
import json

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.twisted.websocket import WebSocketServerFactory, \
    WebSocketServerProtocol

from autobahn.twisted.resource import WebSocketResource

def sign(x):
    return int(np.sign(x))

def move(orig, targ):
    ro, co = orig
    rt, ct = targ
    dr = rt - ro
    dc = ct - co
    if abs(dr) > abs(dc):
        return ro + sign(dr), co
    elif abs(dc) > abs(dr):
        return ro, co + sign(dc)
    else:
        return ro + sign(dr), co + sign(dc)

class EchoServerProtocol(WebSocketServerProtocol):
    def __init__(self):
        super().__init__()
        print("CREATED A SERVER")
        self.frame = 0
        self.packet = {}

    def visVals(self, vals, sz):
      ary = np.zeros((sz, sz, 3))
      vMean = np.mean([e[1] for e in vals])
      vStd  = np.std([e[1] for e in vals])
      nStd, nTol = 4.0, 0.5
      grayVal = int(255 / nStd * nTol)
      for v in vals:
         pos, mat = v
         r, c = pos
         mat = (mat - vMean) / vStd
         color = np.clip(mat, -nStd, nStd)
         color = int(color * 255.0 / nStd)
         if color > 0:
             color = (0, color, 128)
         else:
             color = (-color, 0, 128)
         ary[r, c] = color
      return ary.astype(np.uint8)

    def onOpen(self):
        print("Opened connection to server")
        #packet = json.dumps(data).encode('utf8')
        #self.sendMessage(packet, True)

    def onClose(self, wasClean, code=None, reason=None):
        print('Connection closed')

    #Correct connection method?
    def onConnect(self, request):
        print("WebSocket connection request: {}".format(request))
        realm = self.factory.realm.envs[0]
        self.realm = realm
        self.frame += 1

        gameTiles = realm.world.env.tiles
        sz = gameTiles.shape[0]

        ann = self.realm.sword.anns[0]
        vals = ann.visVals()
        self.vals = self.visVals(vals, sz)

        self.sendUpdate()

    def onMessage(self, packet, isBinary):
        print("Message", packet)

        packet = json.loads(packet)
        #self.sendMessage(payload, isBinary)
        #packet = packet['0']

        pos = packet['pos']
        ent = self.packet['ent']
        ent['0'] = {'pos': move(ent['0']['pos'], pos)}


    def sendUpdate(self):
        ent = {}
        realm = self.realm
        for id, e in realm.desciples.items():
           e = e.client
           pkt = {}
           pkt['pos']  = e.pos
           pkt['entID'] = e.entID
           pkt['color'] = e.color.hex
           pkt['name'] = 'Neural_' + str(e.entID)
           pkt['food'] = e.food
           pkt['water'] = e.water
           pkt['health'] = e.health
           pkt['maxFood'] = e.maxFood
           pkt['maxWater'] = e.maxWater
           pkt['maxHealth'] = e.maxHealth
           pkt['damage'] = e.damage

           pkt['attack'] = None
           pkt['target'] = None
           if e.attack is not None: 
              pkt['attack'] = e.attack.action.__name__
              pkt['target'] = e.attack.args.entID
           ent[id] = pkt
        self.packet['ent'] = ent

        gameMap = realm.env
        self.packet['map'] = gameMap.tolist()

        gameTiles = realm.world.env.tiles
        tiles = []
        for tileList in gameTiles:
           tl = []
           for tile in tileList:
              tl.append(tile.counts.tolist())
           tiles.append(tl)
        self.packet['counts'] = tiles

        self.packet['values'] = self.vals.tolist()
 
        packet = json.dumps(self.packet).encode('utf8')
        self.sendMessage(packet, False)

    def connectionMade(self):
        super().connectionMade()
        self.factory.clientConnectionMade(self)

    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.factory.clientConnectionLost(self)

class WSServerFactory(WebSocketServerFactory):
    def __init__(self, ip, realm, step):
        super().__init__(ip)
        self.realm, self.step = realm, step
        self.clients = []

        lc = LoopingCall(self.announce)
        lc.start(0.6)

    def announce(self):
        self.step()
        for client in self.clients:
            client.sendUpdate()

    def clientConnectionMade(self, client):
        self.clients.append(client)

    def clientConnectionLost(self, client):
        self.clients.remove(client)

class Application:
    def __init__(self, realm, step):
        self.realm = realm
        #log.startLogging(sys.stdout)
        port = 8080

        #factory = WSServerFactory(u'ws://localhost:'+str(port), realm)
        factory = WSServerFactory(u"ws://127.0.0.1:8080", realm, step)
        #factory = WebSocketServerFactory(u"ws://127.0.0.1:8080")
        factory.protocol = EchoServerProtocol

        resource = WebSocketResource(factory)

        # we server static files under "/" ..
        root = File(".")

        # and our WebSocket server under "/ws" (note that Twisted uses
        # bytes for URIs)
        root.putChild(b"ws", resource)

        # both under one Twisted Web Site
        site = Site(root)

        reactor.listenTCP(port, site)
        reactor.run()


