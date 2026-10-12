from config.settings import Settings
from tools.sql_tool import SqlServerTool


def test_subscription_revenue_template_targets_subscription_tables():
    tool = SqlServerTool(Settings())
    sql = tool.generate_sql("Which subscription plans have the highest active contract value?")
    assert "Subscription_Transactions" in sql
    assert "Subscription_Plans" in sql
    tool.validate_sql(sql)


def test_subscription_sla_template_targets_complaints():
    tool = SqlServerTool(Settings())
    sql = tool.generate_sql("Show complaint tickets that breached SLA")
    assert "Complaint_tickets" in sql
    assert "SLA_Hours" in sql
    tool.validate_sql(sql)

