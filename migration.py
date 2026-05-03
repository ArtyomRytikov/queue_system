from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def _table_names(connection) -> set[str]:
    return set(inspect(connection).get_table_names())


def _add_column_if_missing(connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _column_names(connection, table_name):
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def migrate_legacy_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        tables = _table_names(connection)

        if "users" in tables:
            columns = _column_names(connection, "users")
            if "username" in columns:
                _add_column_if_missing(connection, "users", "full_name", "VARCHAR(150)")
                _add_column_if_missing(connection, "users", "email", "VARCHAR(255)")
                _add_column_if_missing(connection, "users", "is_active", "BOOLEAN")
                connection.execute(text("UPDATE users SET full_name = COALESCE(NULLIF(full_name, ''), username)"))
                connection.execute(text("UPDATE users SET email = COALESCE(email, username || '@legacy.local')"))
                connection.execute(text("UPDATE users SET is_active = COALESCE(is_active, TRUE)"))
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))

        if "services" in tables:
            columns = _column_names(connection, "services")
            _add_column_if_missing(connection, "services", "description", "TEXT")
            _add_column_if_missing(connection, "services", "duration_minutes", "INTEGER")
            _add_column_if_missing(connection, "services", "color", "VARCHAR(30)")
            _add_column_if_missing(connection, "services", "created_at", "TIMESTAMP")
            if "avg_service_time_min" in columns:
                connection.execute(
                    text(
                        "UPDATE services "
                        "SET duration_minutes = COALESCE(duration_minutes, avg_service_time_min)"
                    )
                )
            connection.execute(text("UPDATE services SET description = COALESCE(description, '')"))
            connection.execute(text("UPDATE services SET duration_minutes = COALESCE(duration_minutes, 20)"))
            connection.execute(text("UPDATE services SET color = COALESCE(color, '#2f6fed')"))
            connection.execute(text("UPDATE services SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))

        if "windows" in tables:
            _add_column_if_missing(connection, "windows", "location", "VARCHAR(120)")
            _add_column_if_missing(connection, "windows", "is_active", "BOOLEAN")
            _add_column_if_missing(connection, "windows", "created_at", "TIMESTAMP")
            connection.execute(text("UPDATE windows SET location = COALESCE(location, '')"))
            connection.execute(text("UPDATE windows SET is_active = COALESCE(is_active, TRUE)"))
            connection.execute(text("UPDATE windows SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))


def migrate_legacy_data(engine: Engine) -> None:
    with engine.begin() as connection:
        tables = _table_names(connection)
        if "schedule" not in tables or "availability_rules" not in tables or "windows" not in tables:
            return

        rule_count = connection.execute(text("SELECT COUNT(*) FROM availability_rules")).scalar() or 0
        if rule_count:
            return

        windows = [row[0] for row in connection.execute(text("SELECT id FROM windows")).fetchall()]
        schedule_rows = connection.execute(
            text("SELECT day_of_week, time_from, time_to FROM schedule ORDER BY day_of_week, time_from")
        ).fetchall()

        if not windows or not schedule_rows:
            return

        for window_id in windows:
            for day_of_week, time_from, time_to in schedule_rows:
                connection.execute(
                    text(
                        """
                        INSERT INTO availability_rules (
                            window_id,
                            weekday,
                            start_time,
                            end_time,
                            step_minutes,
                            is_active,
                            created_at
                        )
                        VALUES (
                            :window_id,
                            :weekday,
                            :start_time,
                            :end_time,
                            :step_minutes,
                            :is_active,
                            CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "window_id": window_id,
                        "weekday": max(int(day_of_week) - 1, 0),
                        "start_time": time_from,
                        "end_time": time_to,
                        "step_minutes": 30,
                        "is_active": True,
                    },
                )
