# This file makes the src directory a Python package

# Import main components for easier access
try:
    from .api_etke_prod import app
    from .etke_matrix_client_prod import ProductionMatrixClient
    from .postgres_matrix_store import PostgresMatrixStore
except ImportError as e:
    # Handle import errors gracefully for deployment
    import warnings
    warnings.warn(f"Could not import all src components: {e}", ImportWarning)