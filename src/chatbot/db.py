import threading
import sys
import time
import logging
import os
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('hr.chatbot.db')

SHARE_COLLECTION_NAME = 'share'
SHARE_COLLECTION_SIZE = 10000

class ShareDataListener(object):
    def handle_incoming_data(self, data):
        return NotImplemented

class DefaultShareDataListener(ShareDataListener):
    def handle_incoming_data(self, data):
        print 'handle incoming data', data

class MongoDB(object):
    def __init__(self, dbname):
        self.client = None
        self.dbname = dbname
        self.listeners = []
        timer = threading.Timer(0, self._start_monitoring)
        timer.daemon = True
        timer.start()

    def get_share_collection(self):
        collection_names = self.client[self.dbname].collection_names()
        if SHARE_COLLECTION_NAME not in collection_names:
            logger.info("Creating shared collection")
            self.client[self.dbname].create_collection(
                SHARE_COLLECTION_NAME, capped=True, size=SHARE_COLLECTION_SIZE)
        return self.client[self.dbname][SHARE_COLLECTION_NAME]

    def add_listener(self, listener):
        self.listeners.append(listener)

    def _start_monitoring(self):
        import pymongo
        while self.client is None:
            time.sleep(0.1)
        collection = self.get_share_collection()
        while True:
            cursor = collection.find(cursor_type=pymongo.CursorType.TAILABLE_AWAIT, no_cursor_timeout=True)
            try:
                while cursor.alive:
                    for doc in cursor:
                        logger.info('Get document %s', doc)
                        for l in self.listeners:
                            l.handle_incoming_data(doc)
                    time.sleep(0.2)
            except Exception as ex:
                logger.error(traceback.format_exc())
            finally:
                cursor.close()
            logger.warn('Invalid cursor. Retrying')
            time.sleep(2)


def _init_mongodb(mongodb, host='localhost', port=27017, socketTimeoutMS=2000, serverSelectionTimeoutMS=1000):
    import pymongo
    def _init_mongo_client(mongodb):
        while mongodb.client is None:
            mongodb.client = pymongo.MongoClient(
                'mongodb://{}:{}/'.format(host, port),
                socketTimeoutMS=socketTimeoutMS,
                serverSelectionTimeoutMS=serverSelectionTimeoutMS)
            try:
                mongodb.client.admin.command('ismaster')
                logger.warn("Activate mongodb, %s", mongodb)
            except pymongo.errors.ConnectionFailure:
                logger.error("Server not available")
                mongodb.client = None
            time.sleep(0.2)

    timer = threading.Timer(0, _init_mongo_client, (mongodb,))
    timer.daemon = True
    timer.start()
    logger.info("Thread starts")

def get_mongodb(dbname='hr', **kwargs):
    mongodb = MongoDB(dbname)
    _init_mongodb(mongodb, **kwargs)
    return mongodb

if __name__ == '__main__':
    mongodb = get_mongodb()
    while mongodb.client is None:
        time.sleep(0.1)
    print mongodb.client.server_info()
    mongodb.add_listener(DefaultShareDataListener())
    while True:
        time.sleep(1)
