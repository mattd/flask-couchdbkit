from __future__ import with_statement

import unittest
from datetime import datetime

import flask
from flaskext.couchdbkit import CouchDBKit
from couchdbkit.exceptions import BadValueError


def make_todo_model(couchdb):
    class Todo(couchdb.Document):
        title = couchdb.StringProperty()
        text = couchdb.StringProperty()
        done = couchdb.BooleanProperty(default=False)
        pub_date = couchdb.DateTimeProperty(default=datetime.utcnow)
    return Todo


class SchemaTestCase(unittest.TestCase):

    def setUp(self):
        app = flask.Flask(__name__)
        app.config['COUCHDB_DATABASE'] = 'test_db_1'
        app.config['TESTING'] = True
        couchdb = CouchDBKit(app)
        self.Todo = make_todo_model(couchdb)

        self.app = app
        self.couchdb = couchdb
        self.db = self.couchdb.server[self.app.config['COUCHDB_DATABASE']]

    def tearDown(self):
        del self.couchdb.server[self.app.config['COUCHDB_DATABASE']]

    def test_create(self):
        todo = self.Todo(title='First Todo', text='Some text.')
        todo.save()
        self.assertTrue(self.db.doc_exist(todo._id))

    def test_field_validation(self):
        self.assertRaises(BadValueError, self.Todo, title=1, text='More text.')

    def test_retrieve(self):
        todo = self.Todo(title='2nd Todo', text='Some text.')
        todo.save()
        retrieved = self.Todo.get(todo._id)
        self.assertEqual(retrieved.title, '2nd Todo')


class InitializationTestCase(unittest.TestCase):

    def setUp(self):
        app = flask.Flask(__name__)
        app.config['COUCHDB_DATABASE'] = 'test_db_2'
        app.config['TESTING'] = True
        self.app = app

    def tearDown(self):
        del self.couchdb.server[self.app.config['COUCHDB_DATABASE']]

    def test_connection_manager(self):
        self.app.config['COUCHDB_KEEPALIVE'] = 20
        self.couchdb = CouchDBKit(self.app)
        server = self.couchdb.server
        self.assertEqual(server.res.client._manager.max_conn,
                         self.app.config['COUCHDB_KEEPALIVE'])

    def test_init_db(self):
        self.couchdb = CouchDBKit(self.app)
        self.assertTrue(self.couchdb.server.all_dbs().index('test_db_2'))

    def test_late_initialization(self):
        self.couchdb = CouchDBKit()
        self.couchdb.init_app(self.app)
        self.assertTrue(self.couchdb.server.all_dbs().index('test_db_2'))


class DocLoaderTestCase(unittest.TestCase):

    def setUp(self):
        app = flask.Flask(__name__)
        app.config['COUCHDB_DATABASE'] = 'test_db_3'
        app.config['TESTING'] = True
        couchdb = CouchDBKit(app)
        self.Todo = make_todo_model(couchdb)

        self.Todo(title='First Todo', text='Some text.').save()
        self.Todo(title='Second Todo', text='More text.', done=True).save()
        self.Todo(title='Third Todo', text='Even more text.').save()

        self.app = app
        self.couchdb = couchdb

    def tearDown(self):
        del self.couchdb.server[self.app.config['COUCHDB_DATABASE']]

    def test_doc_loader(self):
        self.couchdb.sync()
        results = [row for row in self.Todo.view('todos/status_count',
                   group=True)]
        self.assertFalse(results[0]['key'])
        self.assertEqual(results[0]['value'], 2)


class BasicAppTestCase(unittest.TestCase):

    def setUp(self):
        app = flask.Flask(__name__)
        app.config['COUCHDB_DATABASE'] = 'test_db_4'
        app.config['TESTING'] = True
        couchdb = CouchDBKit(app)
        self.Todo = make_todo_model(couchdb)

        @app.route('/')
        def index():
            return '\n'.join(row['key'] for row in
                             self.Todo.view('todos/all'))

        @app.route('/add', methods=['POST'])
        def add():
            form = flask.request.form
            todo = self.Todo(title=form['title'], text=form['text'])
            todo.save()
            return 'added'

        self.app = app
        self.couchdb = couchdb
        self.couchdb.sync()

    def tearDown(self):
        del self.couchdb.server[self.app.config['COUCHDB_DATABASE']]

    def test_basic_insert(self):
        c = self.app.test_client()
        c.post('/add', data=dict(title='First Item', text='The text'))
        c.post('/add', data=dict(title='Second Item', text='More text'))
        rv = c.get('/')
        self.assertEqual(rv.data, 'First Item\nSecond Item')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SchemaTestCase))
    suite.addTest(unittest.makeSuite(InitializationTestCase))
    suite.addTest(unittest.makeSuite(DocLoaderTestCase))
    suite.addTest(unittest.makeSuite(BasicAppTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
