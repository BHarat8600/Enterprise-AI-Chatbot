import sqlparse
from contextlib import contextmanager


class PostgreSQLTool:
    dialect = "PostgreSQL"

    def __init__(self, settings):
        self.settings = settings

    @property
    def configured(self):
        return bool(self.settings.postgresql_host and self.settings.postgresql_database)

    def connect(self):
        import psycopg

        if not self.configured:
            raise ValueError("PostgreSQL host and database are required")
        return psycopg.connect(
            host=self.settings.postgresql_host,
            port=self.settings.postgresql_port,
            dbname=self.settings.postgresql_database,
            user=self.settings.postgresql_user,
            password=self.settings.postgresql_password,
            sslmode=self.settings.postgresql_sslmode,
            connect_timeout=15,
            options="-c default_transaction_read_only=on -c statement_timeout=60000",
        )

    def validate_sql(self, sql):
        statements = sqlparse.parse(sql)
        if len(statements) != 1 or statements[0].get_type() != "SELECT":
            raise ValueError("Only a single read-only SELECT is permitted")

    def execute_select(self, sql):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns = [c.name for c in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def tables(self):
        return self.execute_select(
            'SELECT table_schema AS "TABLE_SCHEMA", table_name AS "TABLE_NAME" '
            "FROM information_schema.tables WHERE table_type='BASE TABLE' "
            "AND table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema, table_name"
        )

    def columns(self, tables):
        predicate = " OR ".join(
            "(table_schema='"
            + r["TABLE_SCHEMA"].replace("'", "''")
            + "' AND table_name='"
            + r["TABLE_NAME"].replace("'", "''")
            + "')"
            for r in tables
        )
        return self.execute_select(
            'SELECT table_schema AS "TABLE_SCHEMA", table_name AS "TABLE_NAME", '
            'column_name AS "COLUMN_NAME", data_type AS "DATA_TYPE", udt_name, is_nullable, '
            "character_maximum_length, numeric_precision, numeric_scale, column_default, generation_expression "
            "FROM information_schema.columns WHERE "
            + predicate
            + " ORDER BY table_schema, table_name, ordinal_position"
        )

    def relationships(self):
        return self.execute_select(
            "SELECT sn.nspname AS source_schema, st.relname AS source_table, sa.attname AS source_column, "
            "tn.nspname AS target_schema, tt.relname AS target_table, ta.attname AS target_column, "
            "con.conname AS constraint_name, k.ordinality AS key_ordinal FROM pg_constraint con "
            "JOIN pg_class st ON st.oid=con.conrelid JOIN pg_namespace sn ON sn.oid=st.relnamespace "
            "JOIN pg_class tt ON tt.oid=con.confrelid JOIN pg_namespace tn ON tn.oid=tt.relnamespace "
            "CROSS JOIN LATERAL unnest(con.conkey, con.confkey) WITH ORDINALITY AS k(source_id,target_id,ordinality) "
            "JOIN pg_attribute sa ON sa.attrelid=st.oid AND sa.attnum=k.source_id "
            "JOIN pg_attribute ta ON ta.attrelid=tt.oid AND ta.attnum=k.target_id WHERE con.contype='f'"
        )

    def keys(self):
        return self.execute_select(
            "SELECT ns.nspname AS schema_name, t.relname AS table_name, a.attname AS column_name, "
            "i.indisprimary AS is_primary_key, idx.relname AS index_name, k.ordinality AS key_ordinal "
            "FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace ns ON ns.oid=t.relnamespace "
            "JOIN pg_class idx ON idx.oid=i.indexrelid CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum,ordinality) "
            "JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum "
            "WHERE i.indisunique AND i.indisvalid AND i.indisready AND i.indpred IS NULL AND i.indexprs IS NULL AND k.ordinality<=i.indnkeyatts"
        )

    def compile(self, sql):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN (FORMAT JSON) " + sql)
                cursor.fetchall()
                cursor.execute(
                    "SELECT * FROM (" + sql.rstrip().rstrip(";") + ") AS _verified_query LIMIT 0"
                )
                return [c.name for c in cursor.description]

    @contextmanager
    def query_cursor(self, sql):
        with self.connect() as connection:
            with connection.cursor(name="report_cursor") as cursor:
                cursor.execute(sql)
                # psycopg describes the portal during execute; do not prefetch/discard rows.
                yield cursor

    def execute_preview(self, sql):
        with self.query_cursor(sql) as cursor:
            columns = [c[0] for c in cursor.description]
            rows, count = [], 0
            while batch := cursor.fetchmany(1000):
                for row in batch:
                    if len(rows) < 10:
                        rows.append(dict(zip(columns, row, strict=True)))
                count += len(batch)
            return {
                "rows": rows,
                "row_count": count,
                "columns": columns,
                "column_count": len(columns),
            }
