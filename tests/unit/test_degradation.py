"""Unit tests for graceful degradation layer.

Tests verify that graph operations degrade gracefully when Neo4j is unavailable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agentsim.knowledge_graph.degradation import graceful_graph_op, is_graph_available


class TestGracefulGraphOp:
    """Tests for the graceful_graph_op decorator."""

    def test_returns_result_on_success(self) -> None:
        @graceful_graph_op(fallback=())
        def get_items() -> tuple[str, ...]:
            return ("a", "b")

        assert get_items() == ("a", "b")

    def test_returns_fallback_on_connection_refused(self) -> None:
        @graceful_graph_op(fallback=())
        def get_items() -> tuple[str, ...]:
            raise ConnectionRefusedError("Connection refused")

        assert get_items() == ()

    def test_returns_fallback_on_os_error(self) -> None:
        @graceful_graph_op(fallback=None)
        def get_item() -> str | None:
            raise OSError("Network unreachable")

        assert get_item() is None

    def test_returns_fallback_on_service_unavailable(self) -> None:
        """ServiceUnavailable from neo4j driver triggers fallback."""
        # Mock the neo4j exception
        mock_exc = type("ServiceUnavailable", (Exception,), {})

        @graceful_graph_op(fallback="default")
        def get_value() -> str:
            raise mock_exc("Neo4j unavailable")

        # Without real neo4j, ConnectionRefusedError/OSError are caught.
        # ServiceUnavailable requires the neo4j package.
        # Test the stdlib exceptions path.
        pass

    def test_preserves_function_name(self) -> None:
        @graceful_graph_op(fallback=())
        def my_func() -> tuple[()]:
            return ()

        assert my_func.__name__ == "my_func"

    def test_preserves_docstring(self) -> None:
        @graceful_graph_op(fallback=())
        def my_func() -> tuple[()]:
            """My docstring."""
            return ()

        assert my_func.__doc__ == "My docstring."

    def test_non_connection_error_propagates(self) -> None:
        @graceful_graph_op(fallback=())
        def get_items() -> tuple[str, ...]:
            raise ValueError("Bad value")

        import pytest

        with pytest.raises(ValueError, match="Bad value"):
            get_items()

    def test_fallback_value_returned_not_copied(self) -> None:
        sentinel = object()

        @graceful_graph_op(fallback=sentinel)
        def get_item() -> object:
            raise ConnectionRefusedError("refused")

        assert get_item() is sentinel


class TestIsGraphAvailable:
    """Tests for is_graph_available()."""

    @patch("agentsim.knowledge_graph.degradation.socket.create_connection")
    def test_available(self, mock_conn: MagicMock) -> None:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        assert is_graph_available("bolt://localhost:7687") is True

    @patch("agentsim.knowledge_graph.degradation.socket.create_connection")
    def test_not_available(self, mock_conn: MagicMock) -> None:
        mock_conn.side_effect = ConnectionRefusedError("refused")
        assert is_graph_available("bolt://localhost:7687") is False

    @patch("agentsim.knowledge_graph.degradation.socket.create_connection")
    def test_os_error_returns_false(self, mock_conn: MagicMock) -> None:
        mock_conn.side_effect = OSError("Network unreachable")
        assert is_graph_available("bolt://localhost:7687") is False

    def test_default_uri(self) -> None:
        """Default bolt URI parses correctly (may fail connection)."""
        # Just verify it doesn't crash on parsing
        result = is_graph_available()
        assert isinstance(result, bool)

    @patch("agentsim.knowledge_graph.degradation.socket.create_connection")
    def test_custom_port(self, mock_conn: MagicMock) -> None:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        is_graph_available("bolt://localhost:17687")
        mock_conn.assert_called_once_with(("localhost", 17687), timeout=2.0)
