from ephemeral_port_reserve import reserve  # type: ignore

import itertools
import logging
import os
import psycopg2  # type: ignore
import random
import shutil
import signal
import sqlite3
import string
import subprocess
import time
from typing import Dict, List, Optional, Union


class Sqlite3Db(object):
    def __init__(self, path: str) -> None:
        self.path = path
        self.provider = None

    def get_dsn(self) -> None:
        """SQLite3 doesn't provide a DSN, resulting in no CLI-option.
        """
        return None

    def query(self, query: str) -> Union[List[Dict[str, Union[int, bytes]]], List[Dict[str, Optional[int]]], List[Dict[str, str]], List[Dict[str, Union[str, int]]], List[Dict[str, int]]]:
        orig = os.path.join(self.path)
        copy = self.path + ".copy"
        shutil.copyfile(orig, copy)
        db = sqlite3.connect(copy)

        db.row_factory = sqlite3.Row
        c = db.cursor()
        c.execute(query)
        rows = c.fetchall()

        result = []
        for row in rows:
            result.append(dict(zip(row.keys(), row)))

        db.commit()
        c.close()
        db.close()
        return result

    def execute(self, query: str) -> None:
        db = sqlite3.connect(self.path)
        c = db.cursor()
        c.execute(query)
        db.commit()
        c.close()
        db.close()

    def stop(self):
        pass


class PostgresDb(object):
    def __init__(self, dbname, port=5432, user='postgres', password='postgres', host='127.0.0.1'):
        self.dbname = dbname
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.provider = None

    @property
    def conn(self):
        return psycopg2.connect(self.get_dsn())

    def get_dsn(self):
        return f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

    def query(self, query):
        cur = self.conn.cursor()
        cur.execute(query)

        # Collect the results into a list of dicts.
        res = []
        for r in cur:
            t = {}
            # Zip the column definition with the value to get its name.
            for c, v in zip(cur.description, r):
                t[c.name] = v
            res.append(t)
        cur.close()
        return res

    def execute(self, query):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(query)

    def stop(self):
        """Clean up the database.
        """
        conn = psycopg2.connect(
            f"dbname=postgres user={self.user} host={self.host} port={self.port}"
        )
        conn.set_isolation_level( psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT )
        cur = conn.cursor()
        cur.execute("DROP DATABASE {};".format(self.dbname))
        cur.close()

    def __del__(self):
        self.stop()


class SqliteDbProvider(object):
    def __init__(self, directory: str) -> None:
        self.directory = directory

    def start(self) -> None:
        pass

    def get_db(self, node_directory: str, testname: str, node_id: int) -> Sqlite3Db:
        path = os.path.join(
            node_directory,
            'lightningd.sqlite3'
        )
        return Sqlite3Db(path)

    def stop(self) -> None:
        pass


class SystemPostgresDbProvider(object):
    """A PostgreSQL database provider that uses an existing system-wide daemon.

    This uses a system-provided postgres daemon, skipping setup and
    teardown of the daemon itself, and allocating test schemas on
    demand in it. Notice that this is primarily for CI, as it is not
    guaranteed schemas are going to get cleaned up after tests run!

    """

    def __init__(self, directory):
        self.logger = logging.getLogger("SystemPostgresDbProvider")
        self.user = os.environ.get('POSTGRES_USER', 'postgres')
        self.password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
        self.host = os.environ.get('POSTGRES_HOST', '127.0.0.1')
        self.port = int(os.environ.get('POSTGRES_PORT', 5432))
        self.conn = None
        self.databases = []

    def start(self):
        self.logger.info("Starting db_provider (no-op, since it is the system's DB)")


    def stop(self):
        self.logger.info("Stopping db_provider (not really, it's a system-wide DB)")

    def get_db(self, node_directory, testname, node_id):
        # Random suffix to avoid collisions on repeated tests
        nonce = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        dbname = "{}_{}_{}".format(testname, node_id, nonce)

        conn = psycopg2.connect(f"dbname=postgres user={self.user} host={self.host} port={self.port} password={self.password}")
        conn.set_isolation_level( psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT )
        cur = conn.cursor()
        cur.execute("CREATE DATABASE {} TEMPLATE template0;".format(dbname))
        cur.close()
        conn.close()

        db = PostgresDb(
            dbname, user=self.user, password=self.password, host=self.host, port=self.port
        )
        self.databases.append(db)

        return db

class PostgresDbProvider(object):
    def __init__(self, directory):
        self.directory = directory
        self.port = None
        self.proc = None
        print("Starting PostgresDbProvider")

    def locate_path(self):
        # Use `pg_config` to determine correct PostgreSQL installation
        pg_config = shutil.which('pg_config')
        if not pg_config:
            raise ValueError("Could not find `pg_config` to determine PostgreSQL binaries. Is PostgreSQL installed?")

        bindir = subprocess.check_output([pg_config, '--bindir']).decode().rstrip()
        if not os.path.isdir(bindir):
            raise ValueError("Error: `pg_config --bindir` didn't return a proper path: {}".format(bindir))

        initdb = os.path.join(bindir, 'initdb')
        postgres = os.path.join(bindir, 'postgres')
        if os.path.isfile(initdb) and os.path.isfile(postgres):
            if os.access(initdb, os.X_OK) and os.access(postgres, os.X_OK):
                logging.info("Found `postgres` and `initdb` in {}".format(bindir))
                return initdb, postgres

        raise ValueError("Could not find `postgres` and `initdb` binaries in {}".format(bindir))

    def start(self):
        passfile = os.path.join(self.directory, "pgpass.txt")
        # Need to write a tiny file containing the password so `initdb` can
        # pick it up
        with open(passfile, 'w') as f:
            f.write('cltest\n')

        # Look for a postgres directory that isn't taken yet. Not locking
        # since this is run in a single-threaded context, at the start of each
        # test. Multiple workers have separate directories, so they can't
        # trample each other either.
        for i in itertools.count():
            self.pgdir = os.path.join(self.directory, 'pgsql-{}'.format(i))
            if not os.path.exists(self.pgdir):
                break

        initdb, postgres = self.locate_path()
        subprocess.check_call([
            initdb,
            '--pwfile={}'.format(passfile),
            '--pgdata={}'.format(self.pgdir),
            '--auth=trust',
            '--username=postgres',
        ])
        conffile = os.path.join(self.pgdir, 'postgresql.conf')
        with open(conffile, 'a') as f:
            f.write('max_connections = 1000\nshared_buffers = 240MB\n')

        self.port = reserve()
        self.proc = subprocess.Popen([
            postgres,
            '-k', '/tmp/',  # So we don't use /var/lib/...
            '-D', self.pgdir,
            '-p', str(self.port),
            '-F',
            '-i',
        ])
        # Hacky but seems to work ok (might want to make the postgres proc a
        # TailableProc as well if too flaky).
        for i in range(30):
            try:
                conn = psycopg2.connect("dbname=postgres user=postgres host=localhost port={}".format(self.port))
                conn.close()
                break
            except Exception:
                time.sleep(0.5)

    @property
    def conn(self):
        return psycopg2.connect("dbname=template1 user=postgres host=localhost port={}".format(self.port))

    def get_db(self, node_directory, testname, node_id):
        # Random suffix to avoid collisions on repeated tests
        nonce = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        dbname = "{}_{}_{}".format(testname, node_id, nonce)

        cur = self.conn.cursor()
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur.execute("CREATE DATABASE {};".format(dbname))
        cur.close()
        db = PostgresDb(dbname, self.port)
        return db

    def stop(self):
        # Send fast shutdown signal see [1] for details:
        #
        # SIGINT
        #
        # This is the Fast Shutdown mode. The server disallows new connections
        # and sends all existing server processes SIGTERM, which will cause
        # them to abort their current transactions and exit promptly. It then
        # waits for all server processes to exit and finally shuts down. If
        # the server is in online backup mode, backup mode will be terminated,
        # rendering the backup useless.
        #
        # [1] https://www.postgresql.org/docs/9.1/server-shutdown.html
        self.proc.send_signal(signal.SIGINT)
        self.proc.wait()
        shutil.rmtree(self.pgdir)
