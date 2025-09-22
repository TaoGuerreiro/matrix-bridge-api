#!/usr/bin/env python3
"""
Production Configuration Manager for Clever Cloud
Validates and manages all environment variables
"""
import os
import urllib.parse
from typing import Dict, Any, Optional
from loguru import logger


class CleverCloudConfig:
    """Production configuration manager for Clever Cloud deployment"""

    def __init__(self):
        """Initialize configuration with validation"""
        self.errors = []
        self.warnings = []

        # Load and validate configuration
        self._load_matrix_config()
        self._load_database_config()
        self._load_api_config()

        # Report status
        self._report_status()

    def _load_matrix_config(self):
        """Load Matrix/etke.cc configuration"""
        self.matrix_homeserver = os.getenv("ETKE_HOMESERVER", "")
        self.matrix_username = os.getenv("ETKE_USERNAME", "")
        self.matrix_password = os.getenv("ETKE_PASSWORD", "")

        # Validation
        if not self.matrix_homeserver:
            self.errors.append("ETKE_HOMESERVER is required")
        elif not self.matrix_homeserver.startswith("https://"):
            self.warnings.append("ETKE_HOMESERVER should use HTTPS")

        if not self.matrix_username:
            self.errors.append("ETKE_USERNAME is required")
        elif not self.matrix_username.startswith("@"):
            self.errors.append("ETKE_USERNAME should be full Matrix ID (@user:server)")

        if not self.matrix_password:
            self.errors.append("ETKE_PASSWORD is required")
        elif len(self.matrix_password) < 20:
            self.warnings.append("ETKE_PASSWORD seems short for production")

    def _load_database_config(self):
        """Load and validate PostgreSQL configuration"""
        self.database_url = os.getenv("DATABASE_URL", "")
        self.use_postgres = os.getenv("USE_POSTGRES_STORE", "true").lower() == "true"

        self.pg_config = {}

        if self.database_url:
            try:
                # Parse DATABASE_URL
                result = urllib.parse.urlparse(self.database_url)

                if result.scheme not in ["postgres", "postgresql"]:
                    self.errors.append(f"DATABASE_URL scheme should be postgresql://, got: {result.scheme}")

                self.pg_config = {
                    "host": result.hostname,
                    "port": result.port or 5432,
                    "database": result.path[1:] if result.path else "",  # Remove leading slash
                    "user": result.username,
                    "password": result.password
                }

                # Validation
                if not self.pg_config["host"]:
                    self.errors.append("DATABASE_URL missing hostname")
                if not self.pg_config["database"]:
                    self.errors.append("DATABASE_URL missing database name")
                if not self.pg_config["user"]:
                    self.errors.append("DATABASE_URL missing username")
                if not self.pg_config["password"]:
                    self.errors.append("DATABASE_URL missing password")

            except Exception as e:
                self.errors.append(f"Failed to parse DATABASE_URL: {e}")

        elif self.use_postgres:
            self.errors.append("USE_POSTGRES_STORE=true but DATABASE_URL not provided")

    def _load_api_config(self):
        """Load API configuration"""
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("PORT", os.getenv("API_PORT", "8080")))
        self.webhook_url = os.getenv("WEBHOOK_URL", "")

        # Clever Cloud always provides PORT
        if not os.getenv("PORT"):
            self.warnings.append("PORT environment variable not set (expected on Clever Cloud)")

        if self.webhook_url and not self.webhook_url.startswith("https://"):
            self.warnings.append("WEBHOOK_URL should use HTTPS in production")

    def _report_status(self):
        """Report configuration status"""
        if self.errors:
            logger.error("❌ Configuration errors found:")
            for error in self.errors:
                logger.error(f"  - {error}")

        if self.warnings:
            logger.warning("⚠️ Configuration warnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")

        if not self.errors:
            logger.info("✅ Configuration validation passed")

    def is_valid(self) -> bool:
        """Check if configuration is valid for production"""
        return len(self.errors) == 0

    def get_matrix_config(self) -> Dict[str, str]:
        """Get Matrix configuration"""
        return {
            "homeserver": self.matrix_homeserver,
            "username": self.matrix_username,
            "password": self.matrix_password
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return {
            "use_postgres": self.use_postgres,
            "database_url": self.database_url,
            "pg_config": self.pg_config
        }

    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return {
            "host": self.api_host,
            "port": self.api_port,
            "webhook_url": self.webhook_url
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary for debugging"""
        return {
            "valid": self.is_valid(),
            "errors": self.errors,
            "warnings": self.warnings,
            "matrix": {
                "homeserver": self.matrix_homeserver,
                "username": self.matrix_username,
                "password_length": len(self.matrix_password) if self.matrix_password else 0
            },
            "database": {
                "use_postgres": self.use_postgres,
                "has_database_url": bool(self.database_url),
                "pg_host": self.pg_config.get("host", ""),
                "pg_database": self.pg_config.get("database", "")
            },
            "api": {
                "host": self.api_host,
                "port": self.api_port,
                "webhook_configured": bool(self.webhook_url)
            }
        }


# Global configuration instance
config = CleverCloudConfig()