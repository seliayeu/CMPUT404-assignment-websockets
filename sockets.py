#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modifications to the code licensed under CC BY-SA 4.0 by Danila Seliayeu, 
# 2021 https://creativecommons.org/licenses/by-sa/4.0/

import flask
from flask import Flask, request, redirect
from flask.json import jsonify
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

# following code taken from https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py
# which is written by Abram Hindle and licensed under the Apache License Version 2.0
def send_all(msg):
    for client in clients:
        client.put( msg )

def send_all_json(obj):
    send_all( json.dumps(obj) )

clients = list()
class Client:
    def __init__(self):
        self.queue = queue.Queue();
    def put(self, v):
        self.queue.put_nowait(v)
    def get(self):
        return self.queue.get()


class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()        

def set_listener( entity, data ):
    ''' do something with the update ! '''
    send_all_json({ entity: data })

myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    return redirect("/static/index.html") 

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    msg = ws.receive()
    try:
        while True:
            msg = ws.receive()
            print("WS RECV: %s" % msg)
            if (msg is not None):
                packet = json.loads(msg)
                for entity in packet:
                    myWorld.set(entity, packet[entity])
                send_all_json(packet)
            else:
                break
    except Exception as e:
        print(e)

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websockjAet URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    print("uhh")
    client = Client()
    clients.append(client)
    g = gevent.spawn(read_ws, ws, client)
    try:
        while True:
            msg = client.get()
            ws.send(msg)
    except Exception as e:
        print("WS Error %s" % e)
    finally:
        clients.remove(client)
        gevent.kill(g)


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    print(myWorld.world())
    if request.method == "PUT":
        res = request.json
        if not res: 
            res = flask_post_json()
        myWorld.set(entity, res)
        return jsonify(myWorld.get(entity))
    elif request.method == "POST":
        res = request.json
        if not res: res = flask_post_json()
        for key in res:
            myWorld = update(entity, key, res[key])
        return jsonify(myWorld.world())

@app.route("/world", methods=['POST','GET'])    
def world():
    print(myWorld.world())
    print('arr')
    return jsonify(myWorld.world())

@app.route("/entity/<entity>")    
def get_entity(entity):
    return jsonify(myWorld.get(entity))


@app.route("/clear", methods=['POST','GET'])
def clear():
    myWorld.clear()
    return jsonify(myWorld.world())



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
