"""SQLite database interface."""

import json
import os
import sqlite3


class DB(object):
    """Instance of DB interface."""

    connection = None
    queries = {}

    def __init__(self, filename):
        """Initialize db interface.

        Args:
            filename (str): sqlite database file

        """
        self.connection = sqlite3.connect(filename)
        self.connection.row_factory = sqlite3.Row

        # load query templates in dir, map filename to contents
        sql_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'queries'
        )
        self.queries = {
            x.replace('.sql', ''): open(os.path.join(sql_dir, x), 'r').read()
            for x in os.listdir(sql_dir)
            if x.endswith('.sql')
        }

        # run setup script
        self._script(self.queries['setup'])
        del self.queries['setup']

    def insert_activity(self, student_id, event):
        """Save activity event into db.

        Args:
            student_id (str): student activity originated from
            event (object): full event data from client

        Returns:
            bool: if data was inserted
        """
        result = self._modify(
            'insert_activity',
            {
                'id': event['object_id'],
                'student_id': student_id,
                'event_date': event['event_date'],
                'action_type': event['action_type'],
                'json': json.dumps(event)
            }
        )
        return result > 0

    def select_activities(self):
        """Get activities needing to be processed."""
        return self._select(
            'select_activities_to_process'
        )

    def update_activity(self, activity_id):
        """Mark activity as processed."""
        self._modify(
            'update_activity_processed',
            {
                'id': activity_id
            }
        )

    def delete_activities(self, student_id):
        """Delete activities for single student."""
        self._modify(
            'delete_activities_by_student_id',
            {
                'student_id': student_id
            }
        )

    def select_cookie(self, login):
        """Get auth cookie by login."""
        rows = self._select(
            'select_auth_cookie_by_login',
            {'login': login}
        )
        if rows:
            return rows[0]['cookie']

    def insert_cookie(self, login, value):
        """Save auth cookie by login."""
        self._modify(
            'insert_auth_cookie_by_login',
            {
                'login': login,
                'cookie': value
            }
        )

    def _script(self, queries):
        cursor = self.connection.cursor()
        cursor.executescript(queries)

    def _select(self, query, placeholders={}):
        cursor = self.connection.cursor()
        cursor.execute(
            self.queries[query],
            placeholders
        )
        return cursor.fetchall()

    def _modify(self, query, placeholders):
        cursor = self.connection.cursor()
        cursor.execute(
            self.queries[query],
            placeholders
        )
        self.connection.commit()
        return cursor.lastrowid
