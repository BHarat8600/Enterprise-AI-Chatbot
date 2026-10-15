"""Read-only metadata and controlled value probes for the separate deep SQL workflow."""

import json
from decimal import Decimal

from agents.database_agent import validate_read_only


class DeepSqlInspection:
    def __init__(self, tool, distinct_limit=50):
        self.tool = tool
        self.pg = getattr(tool, "dialect", "SQL Server") == "PostgreSQL"
        self.distinct_limit = distinct_limit

    def tables(self):
        if self.pg:
            if not self.tool.configured:
                raise ValueError("PostgreSQL is not configured")
            return self.tool.tables()
        if not (self.tool.settings.sqlserver_dsn or self.tool.settings.sqlserver_host):
            raise ValueError("SQL Server is not configured")
        return self.tool.execute_select(
            "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_SCHEMA,TABLE_NAME"
        )

    def inspect(self, tables):
        if self.pg:
            columns = self.tool.columns(tables)
            relationships, keys = self.tool.relationships(), self.tool.keys()
        else:
            predicate = " OR ".join(
                "(TABLE_SCHEMA=N'"
                + r["TABLE_SCHEMA"].replace("'", "''")
                + "' AND TABLE_NAME=N'"
                + r["TABLE_NAME"].replace("'", "''")
                + "')"
                for r in tables
            )
            columns = self.tool.execute_select(
                "SELECT TABLE_SCHEMA,TABLE_NAME,COLUMN_NAME,DATA_TYPE,IS_NULLABLE,"
                "CHARACTER_MAXIMUM_LENGTH,NUMERIC_PRECISION,NUMERIC_SCALE,"
                "(SELECT cc.definition FROM sys.computed_columns cc WHERE "
                "cc.object_id=OBJECT_ID(QUOTENAME(TABLE_SCHEMA)+'.'+QUOTENAME(TABLE_NAME)) AND cc.name=COLUMN_NAME) AS computed_definition "
                "FROM INFORMATION_SCHEMA.COLUMNS WHERE "
                + predicate
                + " ORDER BY TABLE_SCHEMA,TABLE_NAME,ORDINAL_POSITION"
            )
            relationships = self.tool.execute_select(
                "SELECT f.constraint_object_id AS constraint_id,f.constraint_column_id AS key_ordinal,"
                "OBJECT_SCHEMA_NAME(f.parent_object_id) AS source_schema,OBJECT_NAME(f.parent_object_id) AS source_table,"
                "COL_NAME(f.parent_object_id,f.parent_column_id) AS source_column,"
                "OBJECT_SCHEMA_NAME(f.referenced_object_id) AS target_schema,OBJECT_NAME(f.referenced_object_id) AS target_table,"
                "COL_NAME(f.referenced_object_id,f.referenced_column_id) AS target_column FROM sys.foreign_key_columns f"
            )
            keys = self.tool.execute_select(
                "SELECT s.name AS schema_name,t.name AS table_name,c.name AS column_name,"
                "i.is_primary_key,i.name AS index_name,ic.key_ordinal FROM sys.indexes i "
                "JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id "
                "JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id "
                "JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id "
                "WHERE i.is_unique=1 AND i.is_disabled=0 AND i.has_filter=0 AND ic.key_ordinal>0"
            )
        selected = {(r["TABLE_SCHEMA"], r["TABLE_NAME"]) for r in tables}
        return {
            "columns": columns,
            "relationships": [
                r
                for r in relationships
                if (r["source_schema"], r["source_table"]) in selected
                or (r["target_schema"], r["target_table"]) in selected
            ],
            "unique_keys": [r for r in keys if (r["schema_name"], r["table_name"]) in selected],
        }

    def distinct(self, column, search=None):
        """Identifiers must come from verified metadata; values are escaped SQL literals."""
        dtype = column["DATA_TYPE"].lower()
        supported = {
            "char",
            "nchar",
            "varchar",
            "nvarchar",
            "text",
            "ntext",
            "character",
            "character varying",
            "boolean",
            "bit",
            "tinyint",
            "smallint",
            "int",
            "integer",
            "bigint",
            "decimal",
            "numeric",
            "user-defined",
        }
        if dtype not in supported:
            raise ValueError(
                "Distinct probes are limited to categorical text, boolean, enum and numeric-code columns"
            )

        def quote(name):
            return (
                '"' + name.replace('"', '""') + '"'
                if self.pg
                else "[" + name.replace("]", "]]") + "]"
            )

        name = quote(column["COLUMN_NAME"])
        table = quote(column["TABLE_SCHEMA"]) + "." + quote(column["TABLE_NAME"])
        value = (
            f"CAST({name} AS NVARCHAR(MAX))" if not self.pg and dtype in {"text", "ntext"} else name
        )
        size = self.distinct_limit + 1
        sql = f"SELECT DISTINCT {'' if self.pg else f'TOP {size} '}{value} AS value FROM {table}"
        if search is not None:
            if not isinstance(search, str) or not search or len(search) > 120:
                raise ValueError("Targeted search must be 1-120 characters")
            literal = (
                search.replace("~", "~~").replace("%", "~%").replace("_", "~_").replace("'", "''")
            )
            cast = f"CAST({name} AS TEXT)" if self.pg else f"CAST({name} AS NVARCHAR(MAX))"
            prefix = "" if self.pg else "N"
            sql += f" WHERE LOWER({cast}) LIKE LOWER({prefix}'%{literal}%') ESCAPE '~'"
        sql += " ORDER BY value"
        if self.pg:
            sql += f" LIMIT {size}"
        rows = self.tool.execute_select(sql)
        values, omitted = [], 0
        for row in rows[: self.distinct_limit]:
            item = row["value"]
            if isinstance(item, Decimal):
                item = str(item)
            # Do not turn a shortened label into a seemingly valid filter literal.
            if len(json.dumps(item, default=str, ensure_ascii=False)) > 240:
                omitted += 1
            else:
                values.append(item)
        return {
            "schema": column["TABLE_SCHEMA"],
            "table": column["TABLE_NAME"],
            "column": column["COLUMN_NAME"],
            "search": search,
            "values": values,
            "truncated": len(rows) > self.distinct_limit,
            "omitted_long_values": omitted,
            "scope": "entire column" if search is None else "matching values only",
        }

    def compile(self, sql):
        validate_read_only(sql, self.tool)
        if self.pg:
            names = self.tool.compile(sql)
        else:
            escaped = sql.replace("'", "''")
            description = self.tool.execute_select(
                "SELECT name,system_type_name,error_number,error_message FROM "
                f"sys.dm_exec_describe_first_result_set(N'{escaped}',NULL,0)"
            )
            if not description or any(r.get("error_number") for r in description):
                raise ValueError(
                    " ".join(str(r.get("error_message", "")) for r in description)
                    or "SQL has no result columns"
                )
            names = [r["name"] for r in description]
        if not names or not all(names) or len(names) != len({n.lower() for n in names}):
            raise ValueError("Use unique, non-empty output aliases")
        return names

    def probe(self, sql):
        """Read a bounded diagnostic sample; never materialize or export the final report."""
        names = self.compile(sql)
        if len(names) > 12:
            raise ValueError("Diagnostic queries must select at most 12 relevant columns")
        with self.tool.query_cursor(sql) as cursor:
            columns = [c[0] for c in cursor.description]
            if columns != names:
                raise ValueError("Diagnostic columns differ from verified metadata")
            rows = cursor.fetchmany(6)
        safe_rows, omitted = [], 0
        text_budget = 4000
        for row in rows[:5]:
            item = {}
            for name, value in zip(columns, row, strict=True):
                encoded = json.dumps(value, default=str, ensure_ascii=False)
                if len(encoded) > 300 or len(encoded) > text_budget:
                    item[name] = {"omitted": True, "reason": "long diagnostic value"}
                    omitted += 1
                else:
                    item[name] = json.loads(encoded)
                    text_budget -= len(encoded)
            safe_rows.append(item)
        return {
            "sql": sql,
            "columns": columns,
            "rows": safe_rows,
            "rows_truncated": len(rows) > 5,
            "omitted_cells": omitted,
            "scope": "diagnostic sample, not the final report",
        }
