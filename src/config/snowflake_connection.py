"""
CasePilot — Snowflake Connection Manager
=========================================
Manages Snowflake connections using snowflake-connector-python.
Provides session creation, connection pooling, and context management.

Usage:
    from src.config.snowflake_connection import SnowflakeConnection

    with SnowflakeConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_TIMESTAMP()")
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

import snowflake.connector
import snowflake.connector.cursor
snowflake.connector.cursor.CAN_USE_ARROW_RESULT = False
from snowflake.connector import SnowflakeConnection as SFConnection
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class SnowflakeConnection:
    """
    Snowflake connection manager with context manager support.

    Reads credentials from environment variables and provides
    a clean interface for executing queries against Snowflake.
    """

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
    ):
        """
        Initialize connection parameters.

        Args:
            account: Snowflake account identifier (e.g., 'abc12345.us-east-1')
            user: Snowflake username
            password: Snowflake password
            warehouse: Warehouse to use
            database: Database to use
            schema: Schema to use
            role: Role to use
        """
        self.account = account or os.getenv("SNOWFLAKE_ACCOUNT", "")
        self.user = user or os.getenv("SNOWFLAKE_USER", "")
        self.password = password or os.getenv("SNOWFLAKE_PASSWORD", "")
        self.warehouse = warehouse or os.getenv("SNOWFLAKE_WAREHOUSE", "CASEPILOT_WH")
        self.database = database or os.getenv("SNOWFLAKE_DATABASE", "CASEPILOT_DB")
        self.schema = schema or os.getenv("SNOWFLAKE_SCHEMA", "RAW")
        self.role = role or os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
        self._connection: Optional[SFConnection] = None

    def _validate_credentials(self) -> None:
        """Validate that required credentials are present."""
        missing = []
        if not self.account:
            missing.append("SNOWFLAKE_ACCOUNT")
        if not self.user:
            missing.append("SNOWFLAKE_USER")
        if not self.password:
            missing.append("SNOWFLAKE_PASSWORD")

        if missing:
            raise ValueError(
                f"Missing Snowflake credentials: {', '.join(missing)}. "
                f"Set them in your .env file or pass them directly."
            )

    def connect(self) -> SFConnection:
        """
        Establish a connection to Snowflake.

        Returns:
            Active Snowflake connection object.

        Raises:
            ValueError: If required credentials are missing.
            snowflake.connector.errors.DatabaseError: If connection fails.
        """
        self._validate_credentials()

        try:
            self._connection = snowflake.connector.connect(
                account=self.account,
                user=self.user,
                password=self.password,
                warehouse=self.warehouse,
                database=self.database,
                schema=self.schema,
                role=self.role,
                client_session_keep_alive=True,
                login_timeout=30,
                network_timeout=30,
            )
            logger.info(
                f"Connected to Snowflake: {self.account} | "
                f"DB: {self.database} | Schema: {self.schema}"
            )
            return self._connection

        except snowflake.connector.errors.DatabaseError as e:
            logger.error(f"Failed to connect to Snowflake: {e}")
            raise

    def disconnect(self) -> None:
        """Close the active Snowflake connection."""
        if self._connection and not self._connection.is_closed():
            self._connection.close()
            logger.info("Snowflake connection closed.")
            self._connection = None

    def get_connection(self) -> SFConnection:
        """
        Get the current connection, creating one if needed.

        Returns:
            Active Snowflake connection.
        """
        if self._connection is None or self._connection.is_closed():
            return self.connect()
        return self._connection

    def execute_query(
        self, query: str, params: Optional[tuple] = None
    ) -> list:
        """
        Execute a query and return all results.

        Args:
            query: SQL query string.
            params: Optional query parameters.

        Returns:
            List of result rows.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            logger.debug(f"Query executed. Rows returned: {len(results)}")
            return results
        finally:
            cursor.close()

    def execute_query_df(self, query: str, params: Optional[tuple] = None):
        """
        Execute a query and return results as a pandas DataFrame.
        Includes automatic fallback to cursor.fetchall() if fetch_pandas_all() fails
        due to S3 network/SSL issues.
        """
        import pandas as pd

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            try:
                df = cursor.fetch_pandas_all()
            except Exception as e:
                logger.warning(f"fetch_pandas_all failed ({e}), re-executing query with fetchall fallback")
                cursor.close()
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                df = pd.DataFrame(rows, columns=cols)

            logger.debug(f"Query executed. DataFrame shape: {df.shape}")
            return df
        finally:
            cursor.close()


    def execute_non_query(
        self, query: str, params: Optional[tuple] = None
    ) -> int:
        """
        Execute a non-SELECT query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL statement.
            params: Optional query parameters.

        Returns:
            Number of rows affected.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            row_count = cursor.rowcount
            logger.debug(f"Non-query executed. Rows affected: {row_count}")
            return row_count
        finally:
            cursor.close()

    def execute_many(
        self, query: str, data: list
    ) -> int:
        """
        Execute a query with multiple parameter sets (bulk insert).

        Args:
            query: SQL statement with parameter placeholders.
            data: List of tuples containing parameter values.

        Returns:
            Total number of rows affected.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(query, data)
            row_count = cursor.rowcount
            logger.debug(f"Bulk execute completed. Rows affected: {row_count}")
            return row_count
        except Exception as e:
            logger.warning(f"executemany failed, falling back to sequential execution. Error: {e}")
            row_count = 0
            for params in data:
                cursor.execute(query, params)
                row_count += cursor.rowcount or 1
            return row_count
        finally:
            cursor.close()


    def use_schema(self, schema: str) -> None:
        """
        Switch to a different schema.

        Args:
            schema: Schema name to switch to.
        """
        self.schema = schema
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"USE SCHEMA {self.database}.{schema}")
            logger.info(f"Switched to schema: {schema}")
        finally:
            cursor.close()

    def __enter__(self) -> 'SnowflakeConnection':
        """Enter context manager — establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager — close connection."""
        self.disconnect()

    def __repr__(self) -> str:
        status = "connected" if self._connection and not self._connection.is_closed() else "disconnected"
        return (
            f"SnowflakeConnection(account='{self.account}', "
            f"database='{self.database}', schema='{self.schema}', "
            f"status='{status}')"
        )


def get_connection(**kwargs) -> SnowflakeConnection:
    """
    Factory function to create a SnowflakeConnection instance.

    Args:
        **kwargs: Connection parameters (account, user, password, etc.)

    Returns:
        Configured SnowflakeConnection instance.
    """
    return SnowflakeConnection(**kwargs)
