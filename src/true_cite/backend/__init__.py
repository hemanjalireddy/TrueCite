from .ingestion import PolicyIngestor


global_ingestor = PolicyIngestor()

__all__ = ["PolicyIngestor", "global_ingestor"]