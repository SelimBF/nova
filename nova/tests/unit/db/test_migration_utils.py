# Copyright (c) 2013 Boris Pavlovic (boris@pavlovic.me).
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy import test_base
from oslo_db.sqlalchemy import test_fixtures
from sqlalchemy import Integer, String
from sqlalchemy import MetaData, Table, Column
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.types import UserDefinedType

from nova.db.sqlalchemy import api as db
from nova.db.sqlalchemy import utils
from nova import exception
from nova import test
from nova.tests import fixtures as nova_fixtures


class CustomType(UserDefinedType):
    """Dummy column type for testing unsupported types."""
    def get_col_spec(self):
        return "CustomType"

# TODO(sdague): no tests in the nova/tests tree should inherit from
# base test classes in another library. This causes all kinds of havoc
# in these doing things incorrectly for what we need in subunit
# reporting. This is a long unwind, but should be done in the future
# and any code needed out of oslo_db should be exported / accessed as
# a fixture.


class TestMigrationUtilsSQLite(
        test_fixtures.OpportunisticDBTestMixin, test.NoDBTestCase):
    """Class for testing utils that are used in db migrations."""

    def setUp(self):
        # NOTE(sdague): the oslo_db base test case completely
        # invalidates our logging setup, we actually have to do that
        # before it is called to keep this from vomitting all over our
        # test output.
        self.useFixture(nova_fixtures.StandardLogging())
        super(TestMigrationUtilsSQLite, self).setUp()
        self.engine = enginefacade.writer.get_engine()
        self.meta = MetaData(bind=self.engine)

    def test_check_shadow_table(self):
        table_name = 'test_check_shadow_table'

        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer),
                      Column('c', String(256)))
        table.create()

        # check missing shadow table
        self.assertRaises(NoSuchTableError,
                          utils.check_shadow_table, self.engine, table_name)

        shadow_table = Table(db._SHADOW_TABLE_PREFIX + table_name, self.meta,
                             Column('id', Integer),
                             Column('a', Integer))
        shadow_table.create()

        # check missing column
        self.assertRaises(exception.NovaException,
                          utils.check_shadow_table, self.engine, table_name)

        # check when all is ok
        c = Column('c', String(256))
        shadow_table.create_column(c)
        self.assertTrue(utils.check_shadow_table(self.engine, table_name))

        # check extra column
        d = Column('d', Integer)
        shadow_table.create_column(d)
        self.assertRaises(exception.NovaException,
                          utils.check_shadow_table, self.engine, table_name)

    def test_check_shadow_table_different_types(self):
        table_name = 'test_check_shadow_table_different_types'

        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer))
        table.create()

        shadow_table = Table(db._SHADOW_TABLE_PREFIX + table_name, self.meta,
                             Column('id', Integer, primary_key=True),
                             Column('a', String(256)))
        shadow_table.create()
        self.assertRaises(exception.NovaException,
                          utils.check_shadow_table, self.engine, table_name)

    @test_base.backend_specific('sqlite')
    def test_check_shadow_table_with_unsupported_sqlite_type(self):
        table_name = 'test_check_shadow_table_with_unsupported_sqlite_type'

        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer),
                      Column('c', CustomType))
        table.create()

        shadow_table = Table(db._SHADOW_TABLE_PREFIX + table_name, self.meta,
                             Column('id', Integer, primary_key=True),
                             Column('a', Integer),
                             Column('c', CustomType))
        shadow_table.create()
        self.assertTrue(utils.check_shadow_table(self.engine, table_name))

    def test_create_shadow_table_by_table_instance(self):
        table_name = 'test_create_shadow_table_by_table_instance'
        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer),
                      Column('b', String(256)))
        table.create()
        utils.create_shadow_table(self.engine, table=table)
        self.assertTrue(utils.check_shadow_table(self.engine, table_name))

    def test_create_shadow_table_by_name(self):
        table_name = 'test_create_shadow_table_by_name'

        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer),
                      Column('b', String(256)))
        table.create()
        utils.create_shadow_table(self.engine, table_name=table_name)
        self.assertTrue(utils.check_shadow_table(self.engine, table_name))

    @test_base.backend_specific('sqlite')
    def test_create_shadow_table_not_supported_type(self):
        table_name = 'test_create_shadow_table_not_supported_type'
        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', CustomType))
        table.create()

        utils.create_shadow_table(self.engine,
                                  table_name=table_name,
                                  a=Column('a', CustomType()))
        self.assertTrue(utils.check_shadow_table(self.engine, table_name))

    def test_create_shadow_both_table_and_table_name_are_none(self):
        self.assertRaises(exception.NovaException,
                          utils.create_shadow_table, self.engine)

    def test_create_shadow_both_table_and_table_name_are_specified(self):
        table_name = ('test_create_shadow_both_table_and_table_name_are_'
                      'specified')
        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer))
        table.create()
        self.assertRaises(exception.NovaException,
                          utils.create_shadow_table,
                          self.engine, table=table, table_name=table_name)

    def test_create_duplicate_shadow_table(self):
        table_name = 'test_create_duplicate_shadow_table'
        table = Table(table_name, self.meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer))
        table.create()
        utils.create_shadow_table(self.engine, table_name=table_name)
        self.assertRaises(exception.ShadowTableExists,
                          utils.create_shadow_table,
                          self.engine, table_name=table_name)


class TestMigrationUtilsPostgreSQL(TestMigrationUtilsSQLite):
    FIXTURE = test_fixtures.PostgresqlOpportunisticFixture


class TestMigrationUtilsMySQL(TestMigrationUtilsSQLite):
    FIXTURE = test_fixtures.MySQLOpportunisticFixture
