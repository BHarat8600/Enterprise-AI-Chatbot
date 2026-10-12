import pytest

from config.settings import Settings
from tools.sql_tool import SqlSafetyError, SqlServerTool


def test_select_query_is_allowed():
    tool = SqlServerTool(Settings())
    tool.validate_sql("SELECT TOP 5 * FROM dbo.Customers")


@pytest.mark.parametrize("sql", ["DROP TABLE dbo.Users", "SELECT * FROM A; SELECT * FROM B", "UPDATE A SET x = 1"])
def test_destructive_or_multi_statement_sql_is_blocked(sql):
    tool = SqlServerTool(Settings())
    with pytest.raises(SqlSafetyError):
        tool.validate_sql(sql)

