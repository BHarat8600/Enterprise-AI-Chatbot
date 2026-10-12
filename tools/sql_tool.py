from time import perf_counter
from typing import Any
import re

import sqlparse

from config.settings import Settings
from models.schemas import SourceCitation, ToolName, ToolResult


class SqlSafetyError(ValueError):
    pass


class SqlServerTool:
    destructive_keywords = {
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "truncate",
        "merge",
        "exec",
        "execute",
        "grant",
        "revoke",
    }

    def __init__(self, settings: Settings):
        self.settings = settings

    async def answer(self, query: str) -> ToolResult:
        started = perf_counter()
        try:
            schema = []
            if self.settings.sqlserver_dsn or self.settings.sqlserver_host:
                schema = self.execute_select(
                    "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE "
                    "FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"
                )
            if any(term in query.lower() for term in ["margin", "profitable", "profitability"]):
                return ToolResult(tool=ToolName.sql, success=True,
                    output={"schema": schema, "limitation": "The current SQL templates do not calculate margin or profitability. No margin result was executed. Identify the required revenue and cost columns and calculation from the schema and BRD before answering."},
                    latency_ms=(perf_counter() - started) * 1000)
            sql = self.generate_sql(query)
            self.validate_sql(sql)
            rows = self.execute_select(sql)
            output: dict[str, Any] = {"sql": sql, "rows": rows, "row_count": len(rows), "schema": schema,
                "limitation": "SQL uses predefined templates. Verify that the executed SQL matches the requested scope and business definition before using its results."}
            return ToolResult(
                tool=ToolName.sql,
                success=True,
                output=output,
                latency_ms=(perf_counter() - started) * 1000,
                citations=[SourceCitation(source_id="sqlserver", title="SQL Server", location=sql)],
            )
        except Exception as exc:
            return ToolResult(
                tool=ToolName.sql,
                success=False,
                output=None,
                latency_ms=(perf_counter() - started) * 1000,
                error=str(exc),
            )

    def generate_sql(self, query: str) -> str:
        if re.match(r"^\s*(select\b|with\b)", query, re.IGNORECASE):
            return query
        lower = query.lower()
        if any(word in lower for word in ["subscription", "society", "payment", "complaint", "ticket", "sla", "plan"]):
            return self._generate_subscription_sql(lower)
        if "product" in lower and any(word in lower for word in ["revenue", "sales", "top"]):
            revenue = "NetRevenue" if "net" in lower else "Quantity * UnitPrice"
            return (
                f"SELECT TOP 10 ProductName, Category, SUM({revenue}) AS Revenue "
                "FROM dbo.ProductSales GROUP BY ProductName, Category ORDER BY Revenue DESC"
            )
        if "product" in lower:
            return "SELECT TOP 20 * FROM dbo.ProductSales ORDER BY SaleDate DESC"
        return "SELECT TOP 10 TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME"

    def _generate_subscription_sql(self, lower_query: str) -> str:
        if "schema" in lower_query or "columns" in lower_query or "tables" in lower_query:
            return (
                "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME IN ('Society_Master_Data','Subscription_Plans',"
                "'Subscription_Transactions','Payment_Gateway','Complaint_tickets') "
                "ORDER BY TABLE_NAME, ORDINAL_POSITION"
            )
        if "complaint" in lower_query or "ticket" in lower_query or "sla" in lower_query:
            if any(word in lower_query for word in ["breach", "overdue", "late"]):
                return (
                    "SELECT TOP 20 s.SocietyName, c.Category, c.CreatedDate, c.ResolvedDate, "
                    "c.SLA_Hours, c.Status, DATEDIFF(hour, c.CreatedDate, COALESCE(c.ResolvedDate, GETDATE())) AS HoursTaken "
                    "FROM dbo.Complaint_tickets c JOIN dbo.Society_Master_Data s ON s.SocietyID = c.SocietyID "
                    "WHERE DATEDIFF(hour, c.CreatedDate, COALESCE(c.ResolvedDate, GETDATE())) > c.SLA_Hours "
                    "ORDER BY HoursTaken DESC"
                )
            return (
                "SELECT TOP 20 s.SocietyName, c.Category, c.Status, c.SLA_Hours, c.CreatedDate, c.ResolvedDate "
                "FROM dbo.Complaint_tickets c JOIN dbo.Society_Master_Data s ON s.SocietyID = c.SocietyID "
                "ORDER BY c.CreatedDate DESC"
            )
        if "payment" in lower_query or "gateway" in lower_query or "amount" in lower_query:
            if any(word in lower_query for word in ["failed", "failure", "pending"]):
                return (
                    "SELECT TOP 20 s.SocietyName, p.Amount, p.PaymentMethod, p.Status, p.PaymentDate "
                    "FROM dbo.Payment_Gateway p JOIN dbo.Society_Master_Data s ON s.SocietyID = p.SocietyID "
                    "WHERE p.Status <> 'Success' ORDER BY p.PaymentDate DESC"
                )
            return (
                "SELECT TOP 10 s.SocietyName, SUM(p.Amount) AS TotalPaid "
                "FROM dbo.Payment_Gateway p JOIN dbo.Society_Master_Data s ON s.SocietyID = p.SocietyID "
                "WHERE p.Status = 'Success' GROUP BY s.SocietyName ORDER BY TotalPaid DESC"
            )
        if "revenue" in lower_query or "mrr" in lower_query or "arr" in lower_query:
            return (
                "SELECT TOP 10 sp.PlanName, COUNT(*) AS ActiveSubscriptions, SUM(sp.Price) AS ContractValue "
                "FROM dbo.Subscription_Transactions st JOIN dbo.Subscription_Plans sp ON sp.PlanID = st.PlanID "
                "WHERE st.Status = 'Active' GROUP BY sp.PlanName ORDER BY ContractValue DESC"
            )
        if "expired" in lower_query or "expiring" in lower_query or "renewal" in lower_query:
            return (
                "SELECT TOP 20 s.SocietyName, sp.PlanName, st.EndDate, st.Status "
                "FROM dbo.Subscription_Transactions st "
                "JOIN dbo.Society_Master_Data s ON s.SocietyID = st.SocietyID "
                "JOIN dbo.Subscription_Plans sp ON sp.PlanID = st.PlanID "
                "WHERE st.Status <> 'Active' OR st.EndDate <= DATEADD(day, 30, CAST(GETDATE() AS date)) "
                "ORDER BY st.EndDate"
            )
        if "city" in lower_query or "state" in lower_query or "flat" in lower_query:
            return (
                "SELECT City, State, COUNT(*) AS Societies, SUM(TotalFlats) AS TotalFlats "
                "FROM dbo.Society_Master_Data GROUP BY City, State ORDER BY TotalFlats DESC"
            )
        return (
            "SELECT TOP 20 s.SocietyName, s.City, s.State, s.TotalFlats, sp.PlanName, "
            "st.StartDate, st.EndDate, st.Status "
            "FROM dbo.Subscription_Transactions st "
            "JOIN dbo.Society_Master_Data s ON s.SocietyID = st.SocietyID "
            "JOIN dbo.Subscription_Plans sp ON sp.PlanID = st.PlanID "
            "ORDER BY st.EndDate DESC"
        )

    def validate_sql(self, sql: str) -> None:
        statements = [statement for statement in sqlparse.parse(sql) if statement.tokens]
        if len(statements) != 1:
            raise SqlSafetyError("Only one SQL statement is allowed")
        normalized = " ".join(token.value.lower() for token in statements[0].flatten())
        first = statements[0].get_type().lower()
        if first != "select":
            raise SqlSafetyError("Only SELECT queries are allowed")
        if any(keyword in normalized.split() for keyword in self.destructive_keywords):
            raise SqlSafetyError("Destructive SQL keywords are blocked")

    def execute_select(self, sql: str) -> list[dict[str, Any]]:
        if not (self.settings.sqlserver_dsn or self.settings.sqlserver_host):
            return [{"notice": "SQL Server is not configured. Set SQLSERVER_DSN or host credentials.", "sql": sql}]
        import pyodbc

        conn_str = self.connection_string()
        with pyodbc.connect(conn_str, timeout=15) as connection:
            connection.timeout = 60
            cursor = connection.cursor()
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def execute_preview(self, sql: str) -> dict[str, Any]:
        """Count one result set without materializing all rows or querying twice."""
        import pyodbc

        with pyodbc.connect(self.connection_string(), timeout=15) as connection:
            connection.timeout = 60
            cursor = connection.cursor()
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description]
            if not all(columns) or len(columns) != len({name.lower() for name in columns}):
                raise ValueError("Output columns require unique names")
            rows, count = [], 0
            while batch := cursor.fetchmany(1000):
                for row in batch:
                    if len(rows) < 10:
                        rows.append(dict(zip(columns, row, strict=True)))
                count += len(batch)
            return {"rows": rows, "row_count": count, "columns": columns, "column_count": len(columns)}

    def connection_string(self) -> str:
        if self.settings.sqlserver_dsn:
            return f"DSN={self.settings.sqlserver_dsn};"
        if not self.settings.sqlserver_host:
            raise ValueError("SQLSERVER_HOST is not configured")
        if self.settings.sqlserver_trusted_connection:
            return (
                f"DRIVER={{{self.settings.sqlserver_driver}}};"
                f"SERVER={self.settings.sqlserver_host};DATABASE={self.settings.sqlserver_database};"
                f"Trusted_Connection=yes;Encrypt={self._yes_no(self.settings.sqlserver_encrypt)};"
                "TrustServerCertificate=yes;"
            )
        return (
            f"DRIVER={{{self.settings.sqlserver_driver}}};"
            f"SERVER={self.settings.sqlserver_host};DATABASE={self.settings.sqlserver_database};"
            f"UID={self.settings.sqlserver_user};PWD={self.settings.sqlserver_password};"
            f"Encrypt={self._yes_no(self.settings.sqlserver_encrypt)};TrustServerCertificate=yes;"
        )

    def diagnostics(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "configured": bool(self.settings.sqlserver_dsn or self.settings.sqlserver_host),
            "dsn": self.settings.sqlserver_dsn,
            "host": self.settings.sqlserver_host,
            "database": self.settings.sqlserver_database,
            "driver": self.settings.sqlserver_driver,
            "trusted_connection": self.settings.sqlserver_trusted_connection,
            "encrypt": self.settings.sqlserver_encrypt,
            "connected": False,
        }
        try:
            import pyodbc

            info["installed_drivers"] = list(pyodbc.drivers())
            info["connection_string_preview"] = self._safe_connection_string_preview()
            if not info["configured"]:
                info["error"] = "SQL Server is not configured. Set SQLSERVER_HOST and SQLSERVER_DATABASE in .env, then restart the API."
                return info
            with pyodbc.connect(self.connection_string(), timeout=10) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name")
                row = cursor.fetchone()
                info["connected"] = True
                info["database_name"] = row.database_name
                info["server_name"] = row.server_name
        except Exception as exc:
            info["error"] = str(exc)
        return info

    def _safe_connection_string_preview(self) -> str:
        if self.settings.sqlserver_dsn:
            return f"DSN={self.settings.sqlserver_dsn};"
        auth = "Trusted_Connection=yes;" if self.settings.sqlserver_trusted_connection else "UID=***;PWD=***;"
        return (
            f"DRIVER={{{self.settings.sqlserver_driver}}};"
            f"SERVER={self.settings.sqlserver_host};DATABASE={self.settings.sqlserver_database};"
            f"{auth}Encrypt={self._yes_no(self.settings.sqlserver_encrypt)};TrustServerCertificate=yes;"
        )

    def _yes_no(self, value: bool) -> str:
        return "yes" if value else "no"
