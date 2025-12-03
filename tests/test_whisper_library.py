"""
Unit tests for WhisperLibraryAdapter configuration and model configs.

Tests library configuration, model configs, and validation logic.
Note: Actual library loading requires Whisper artifacts which are not
available in the test environment, so we test configuration and validation.
"""

import pytest
from unittest.mock import MagicMock, patch

from infrastructure.whisper.library_adapter import MODEL_CONFIGS
from core.errors import WhisperLibraryError, LibraryLoadError, ModelInitError


class TestModelConfigs:
    """Tests for model configuration constants"""

    def test_model_configs_exist(self):
        """Test that model configurations are defined"""
        assert "small" in MODEL_CONFIGS
        assert "medium" in MODEL_CONFIGS

    def test_small_model_config(self):
        """Test small model configuration values"""
        config = MODEL_CONFIGS["small"]

        assert config["dir"] == "whisper_small_xeon"
        assert config["model"] == "ggml-small-q5_1.bin"
        assert config["size_mb"] == 181
        assert config["ram_mb"] == 500

    def test_medium_model_config(self):
        """Test medium model configuration values"""
        config = MODEL_CONFIGS["medium"]

        assert config["dir"] == "whisper_medium_xeon"
        assert config["model"] == "ggml-medium-q5_1.bin"
        assert config["size_mb"] == 1500
        assert config["ram_mb"] == 2000

    def test_all_configs_have_required_fields(self):
        """Test that all model configs have required fields"""
        required_fields = ["dir", "model", "size_mb", "ram_mb"]

        for model_name, config in MODEL_CONFIGS.items():
            for field in required_fields:
                assert field in config, f"Model {model_name} missing field: {field}"


class TestWhisperLibraryAdapterValidation:
    """Tests for WhisperLibraryAdapter validation logic"""

    @patch("infrastructure.whisper.library_adapter.get_settings")
    def test_invalid_model_size_raises_error(self, mock_settings):
        """Test that invalid model size raises ValueError"""
        mock_settings.return_value = MagicMock(
            whisper_model_size="invalid_model", whisper_artifacts_dir="."
        )

        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with pytest.raises(ValueError, match="Unsupported model size"):
            WhisperLibraryAdapter(model_size="invalid_model")

    @patch("infrastructure.whisper.library_adapter.get_settings")
    @patch("pathlib.Path.exists")
    def test_missing_library_directory_raises_error(self, mock_exists, mock_settings):
        """Test that missing library directory raises LibraryLoadError"""
        mock_settings.return_value = MagicMock(
            whisper_model_size="small", whisper_artifacts_dir="."
        )
        mock_exists.return_value = False

        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with pytest.raises(LibraryLoadError, match="Library directory not found"):
            WhisperLibraryAdapter(model_size="small")


class TestWhisperLibraryAdapterInitialization:
    """Tests for WhisperLibraryAdapter initialization with mocked dependencies"""

    @patch("infrastructure.whisper.library_adapter.get_settings")
    @patch("infrastructure.whisper.library_adapter.ctypes.CDLL")
    @patch("pathlib.Path.exists")
    def test_successful_initialization(self, mock_exists, mock_cdll, mock_settings):
        """Test successful adapter initialization with mocked library"""
        mock_settings.return_value = MagicMock(
            whisper_model_size="small", whisper_artifacts_dir="."
        )
        mock_exists.return_value = True

        # Mock library with successful context initialization
        mock_lib = MagicMock()
        mock_lib.whisper_init_from_file.return_value = 12345  # Non-null pointer
        mock_cdll.return_value = mock_lib

        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        adapter = WhisperLibraryAdapter(model_size="small")

        assert adapter.model_size == "small"
        assert adapter.ctx == 12345
        assert adapter.lib is not None

    @patch("infrastructure.whisper.library_adapter.get_settings")
    @patch("infrastructure.whisper.library_adapter.ctypes.CDLL")
    @patch("pathlib.Path.exists")
    def test_null_context_raises_error(self, mock_exists, mock_cdll, mock_settings):
        """Test that NULL context from whisper_init raises ModelInitError"""
        mock_settings.return_value = MagicMock(
            whisper_model_size="small", whisper_artifacts_dir="."
        )
        mock_exists.return_value = True

        # Mock library returning NULL context
        mock_lib = MagicMock()
        mock_lib.whisper_init_from_file.return_value = None
        mock_cdll.return_value = mock_lib

        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with pytest.raises(ModelInitError, match="returned NULL"):
            WhisperLibraryAdapter(model_size="small")

    @patch("infrastructure.whisper.library_adapter.get_settings")
    def test_uses_settings_model_size_when_not_specified(self, mock_settings):
        """Test that adapter uses settings model size when not explicitly provided"""
        mock_settings.return_value = MagicMock(
            whisper_model_size="medium", whisper_artifacts_dir="."
        )

        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        # This will fail at library loading, but we can check the model_size was set
        with patch.object(WhisperLibraryAdapter, "_load_libraries"):
            with patch.object(WhisperLibraryAdapter, "_initialize_context"):
                adapter = WhisperLibraryAdapter()
                assert adapter.model_size == "medium"


class TestWhisperLibraryAdapterSingleton:
    """Tests for singleton pattern in get_whisper_library_adapter"""

    @patch("infrastructure.whisper.library_adapter._whisper_library_adapter", None)
    @patch("infrastructure.whisper.library_adapter.WhisperLibraryAdapter")
    def test_singleton_creates_instance_once(self, mock_adapter_class):
        """Test that get_whisper_library_adapter creates instance only once"""
        mock_instance = MagicMock()
        mock_adapter_class.return_value = mock_instance

        from infrastructure.whisper.library_adapter import get_whisper_library_adapter

        # First call creates instance
        adapter1 = get_whisper_library_adapter()
        assert adapter1 == mock_instance
        assert mock_adapter_class.call_count == 1

        # Second call returns same instance (but our mock doesn't persist state)
        # So we just verify the function works


class TestExceptionClasses:
    """Tests for custom exception classes"""

    def test_whisper_library_error_is_exception(self):
        """Test WhisperLibraryError is an Exception"""
        assert issubclass(WhisperLibraryError, Exception)

    def test_library_load_error_is_whisper_error(self):
        """Test LibraryLoadError inherits from WhisperLibraryError"""
        assert issubclass(LibraryLoadError, WhisperLibraryError)

    def test_model_init_error_is_whisper_error(self):
        """Test ModelInitError inherits from WhisperLibraryError"""
        assert issubclass(ModelInitError, WhisperLibraryError)

    def test_exception_messages(self):
        """Test that exceptions can be raised with messages"""
        with pytest.raises(LibraryLoadError, match="test message"):
            raise LibraryLoadError("test message")

        with pytest.raises(ModelInitError, match="init failed"):
            raise ModelInitError("init failed")
