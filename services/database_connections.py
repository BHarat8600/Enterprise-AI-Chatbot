from models.schemas import DatabaseConfig
from tools.sql_tool import SqlServerTool


def connection_settings(defaults, config: DatabaseConfig):
    """Resolve overrides without mutating defaults or forwarding secrets to a model."""
    prefix = config.engine
    fields = {"host": "host", "database": "database", "username": "user"}
    if prefix == "sqlserver":
        fields.update(
            driver="driver", dsn="dsn", trusted_connection="trusted_connection", encrypt="encrypt"
        )
    else:
        fields.update(port="port", sslmode="sslmode")

    def identity(value):
        return value or None if isinstance(value, str) else value

    changes = {
        f"{prefix}_{target}": getattr(config, source)
        for source, target in fields.items()
        if getattr(config, source) is not None
    }
    changed_identity = any(
        source in {"host", "port", "database", "username", "dsn"}
        and getattr(config, source) is not None
        and identity(getattr(config, source))
        != identity(getattr(defaults, f"{prefix}_{target}", None))
        for source, target in fields.items()
    )
    if prefix == "sqlserver" and config.host is not None and config.dsn is None:
        changes["sqlserver_dsn"] = None
    if config.password is not None:
        changes[f"{prefix}_password"] = config.password.get_secret_value()
    elif changed_identity:
        # Never reuse the .env password against a different server/account.
        changes[f"{prefix}_password"] = None
    return defaults.model_copy(update=changes)


def database_tool(defaults, config: DatabaseConfig):
    resolved = connection_settings(defaults, config)
    if config.engine == "postgresql":
        from tools.postgresql_tool import PostgreSQLTool

        return PostgreSQLTool(resolved)
    return SqlServerTool(resolved)


def public_database_defaults(settings):
    return {
        "sqlserver": {
            "engine": "sqlserver",
            "host": settings.sqlserver_host or "",
            "database": settings.sqlserver_database or "",
            "username": settings.sqlserver_user or "",
            "driver": settings.sqlserver_driver,
            "dsn": settings.sqlserver_dsn or "",
            "trusted_connection": settings.sqlserver_trusted_connection,
            "encrypt": settings.sqlserver_encrypt,
            "password_configured": bool(settings.sqlserver_password),
        },
        "postgresql": {
            "engine": "postgresql",
            "host": settings.postgresql_host or "",
            "port": settings.postgresql_port,
            "database": settings.postgresql_database or "",
            "username": settings.postgresql_user or "",
            "sslmode": settings.postgresql_sslmode,
            "password_configured": bool(settings.postgresql_password),
        },
    }
