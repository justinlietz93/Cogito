"""
Configuration loader for the Critique Council application.

This module provides utilities for loading and accessing configuration settings
from the centralized YAML configuration file.
"""

import os
import yaml
from typing import Dict, Any, Optional

class ConfigLoader:
    """
    Configuration loader for the Critique Council application.
    
    This class loads configuration settings from the YAML configuration file
    and provides access to them through a unified interface.
    """
    
    def __init__(self, config_path: str | None = None, *, eager_load: bool = False):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the YAML configuration file. If not provided,
                        defaults to 'config.yaml' in the project root.
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.yaml'
        )
        self._config: Optional[Dict[str, Any]] = None
        if eager_load:
            self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from the YAML file.
        
        Returns:
            Dictionary containing the configuration settings. Missing configuration
            files result in an empty dictionary so optional tooling can import the
            loader without crashing.
            
        Raises:
            yaml.YAMLError: If the configuration file has invalid YAML syntax.
        """
        if not os.path.exists(self.config_path):
            return {}
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Error parsing YAML configuration: {str(e)}")
            
    def _ensure_loaded(self) -> None:
        if self._config is None:
            self._config = self._load_config()

    @property
    def config(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return self._config or {}

    @config.setter
    def config(self, value: Optional[Dict[str, Any]]) -> None:
        self._config = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get a specific section from the configuration.
        
        Args:
            section: Name of the configuration section to retrieve.
            
        Returns:
            Dictionary containing the section's configuration settings.
            Returns an empty dictionary if the section is not found.
        """
        return self.config.get(section, {})
        
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration value.
        
        Args:
            section: Name of the configuration section.
            key: Configuration key within the section.
            default: Default value to return if the key is not found.
            
        Returns:
            The configuration value, or the default if not found.
        """
        section_data = self.get_section(section)
        return section_data.get(key, default)
        
    def get_latex_config(self) -> Dict[str, Any]:
        """
        Get the LaTeX configuration section.
        
        Returns:
            Dictionary containing the LaTeX configuration settings.
        """
        return self.get_section('latex')
        
    def get_api_config(self) -> Dict[str, Any]:
        """
        Get the API configuration section.
        
        Returns:
            Dictionary containing the API configuration settings.
        """
        return self.get_section('api')
        
    def get_reasoning_tree_config(self) -> Dict[str, Any]:
        """
        Get the reasoning tree configuration section.
        
        Returns:
            Dictionary containing the reasoning tree configuration settings.
        """
        return self.get_section('reasoning_tree')
        
    def get_council_orchestrator_config(self) -> Dict[str, Any]:
        """
        Get the council orchestrator configuration section.
        
        Returns:
            Dictionary containing the council orchestrator configuration settings.
        """
        return self.get_section('council_orchestrator')


# Global configuration loader instance
# This can be imported and used throughout the application
config_loader = ConfigLoader()
