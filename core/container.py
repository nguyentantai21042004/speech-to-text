"""
Dependency Injection Container.

This module provides a simple DI container for managing interface implementations.
"""

from typing import Any, Dict, Type, TypeVar, Optional, Callable

from core.logger import logger

T = TypeVar("T")


class Container:
    """
    Simple Dependency Injection Container.

    Supports:
    - Singleton instances (register)
    - Factory functions (register_factory)
    - Interface resolution (resolve)
    """

    _instances: Dict[Type, Any] = {}
    _factories: Dict[Type, Callable[[], Any]] = {}
    _providers: Dict[Type, Callable[[], Any]] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, interface: Type[T], instance: Any) -> None:
        """
        Register a singleton instance for an interface.

        Args:
            interface: The interface type (e.g., ITranscriber)
            instance: The implementation instance
        """
        cls._instances[interface] = instance

    @classmethod
    def register_factory(cls, interface: Type[T], factory: Callable[[], T]) -> None:
        """
        Register a factory function for an interface.
        Factory is called each time resolve() is called.

        Args:
            interface: The interface type
            factory: Factory function that returns an implementation
        """
        cls._providers[interface] = factory

    @classmethod
    def resolve(cls, interface: Type[T]) -> T:
        """
        Resolve an interface to its implementation.

        Args:
            interface: The interface type to resolve

        Returns:
            The registered implementation

        Raises:
            KeyError: If no implementation is registered for the interface
        """
        if interface in cls._instances:
            return cls._instances[interface]
        if interface in cls._providers:
            return cls._providers[interface]()
        raise KeyError(f"No provider registered for {interface.__name__}")

    @classmethod
    def is_registered(cls, interface: Type[T]) -> bool:
        """
        Check if an interface has a registered implementation.

        Args:
            interface: The interface type to check

        Returns:
            True if registered, False otherwise
        """
        return interface in cls._instances or interface in cls._providers

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (useful for testing)."""
        cls._instances.clear()
        cls._factories.clear()
        cls._providers.clear()
        cls._initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if container has been bootstrapped."""
        return cls._initialized

    @classmethod
    def _mark_initialized(cls) -> None:
        """Mark container as initialized."""
        cls._initialized = True


def bootstrap_container() -> None:
    """
    Initialize the dependency injection container.

    Registers all interface implementations:
    - ITranscriber -> WhisperLibraryAdapter
    - IAudioDownloader -> HttpAudioDownloader
    - TranscribeService -> TranscribeService (with injected dependencies)

    This function is idempotent - calling it multiple times has no effect
    after the first successful initialization.
    """
    if Container.is_initialized():
        return

    logger.info("Bootstrapping dependency injection container...")

    try:
        # Import interfaces
        from interfaces.transcriber import ITranscriber
        from interfaces.audio_downloader import IAudioDownloader

        # Import implementations
        from infrastructure.whisper.library_adapter import get_whisper_library_adapter
        from infrastructure.minio.audio_downloader import get_minio_audio_downloader

        # Import services
        from services.transcription import TranscribeService

        # Register all components

        # Register ITranscriber -> WhisperLibraryAdapter (singleton via factory)
        Container.register_factory(ITranscriber, get_whisper_library_adapter)
        logger.info("Registered ITranscriber -> WhisperLibraryAdapter (factory)")

        # Register IAudioDownloader -> MinioAudioDownloader (singleton via factory)
        # Supports both minio:// and http:// URLs
        Container.register_factory(IAudioDownloader, get_minio_audio_downloader)
        logger.info("Registered IAudioDownloader -> MinioAudioDownloader (factory)")

        # Register TranscribeService with injected dependencies
        def create_transcribe_service() -> TranscribeService:
            transcriber = Container.resolve(ITranscriber)
            audio_downloader = Container.resolve(IAudioDownloader)
            return TranscribeService(
                transcriber=transcriber,
                audio_downloader=audio_downloader,
            )

        Container.register_factory(TranscribeService, create_transcribe_service)
        logger.info("Registered TranscribeService with DI (factory)")

        Container._mark_initialized()
        logger.info("Dependency injection container bootstrapped successfully")

    except Exception as e:
        logger.error(f"Failed to bootstrap container: {e}")
        logger.exception("Container bootstrap error details:")
        raise


def get_transcriber():
    """
    Get ITranscriber implementation from container.

    Returns:
        ITranscriber implementation
    """
    from interfaces.transcriber import ITranscriber

    if not Container.is_initialized():
        bootstrap_container()

    return Container.resolve(ITranscriber)


def get_audio_downloader():
    """
    Get IAudioDownloader implementation from container.

    Returns:
        IAudioDownloader implementation
    """
    from interfaces.audio_downloader import IAudioDownloader

    if not Container.is_initialized():
        bootstrap_container()

    return Container.resolve(IAudioDownloader)


def get_transcribe_service():
    """
    Get TranscribeService from container.

    Returns:
        TranscribeService with injected dependencies
    """
    from services.transcription import TranscribeService

    if not Container.is_initialized():
        bootstrap_container()

    return Container.resolve(TranscribeService)
