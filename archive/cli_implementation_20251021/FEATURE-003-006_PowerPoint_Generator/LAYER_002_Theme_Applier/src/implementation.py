"""Theme Applier module for applying themes to UI components."""

from typing import Dict, Any, List, Optional, Union
import json
import os
from pathlib import Path


class ThemeNotFoundError(Exception):
    """Raised when a theme is not found."""
    pass


class InvalidThemeError(Exception):
    """Raised when a theme is invalid."""
    pass


class ThemeApplier:
    """Applies themes to UI components."""
    
    def __init__(self, theme_directory: Optional[str] = None):
        """
        Initialize the ThemeApplier.
        
        Args:
            theme_directory: Optional directory path containing theme files
        """
        self.theme_directory = theme_directory or os.path.join(os.getcwd(), 'themes')
        self._themes_cache: Dict[str, Dict[str, Any]] = {}
        self._current_theme: Optional[str] = None
        self._custom_themes: Dict[str, Dict[str, Any]] = {}
        
    def load_theme(self, theme_name: str) -> Dict[str, Any]:
        """
        Load a theme by name.
        
        Args:
            theme_name: Name of the theme to load
            
        Returns:
            Dictionary containing theme configuration
            
        Raises:
            ThemeNotFoundError: If theme is not found
            InvalidThemeError: If theme file is invalid
        """
        # Check custom themes first
        if theme_name in self._custom_themes:
            return self._custom_themes[theme_name].copy()
            
        # Check cache
        if theme_name in self._themes_cache:
            return self._themes_cache[theme_name].copy()
            
        # Try to load from file
        theme_path = os.path.join(self.theme_directory, f"{theme_name}.json")
        
        if not os.path.exists(theme_path):
            # Try with .theme extension
            theme_path = os.path.join(self.theme_directory, f"{theme_name}.theme")
            
        if not os.path.exists(theme_path):
            raise ThemeNotFoundError(f"Theme '{theme_name}' not found")
            
        try:
            with open(theme_path, 'r') as f:
                theme_data = json.load(f)
                
            if not isinstance(theme_data, dict):
                raise InvalidThemeError(f"Theme '{theme_name}' is not a valid dictionary")
                
            self._themes_cache[theme_name] = theme_data
            return theme_data.copy()
            
        except json.JSONDecodeError as e:
            raise InvalidThemeError(f"Invalid JSON in theme '{theme_name}': {str(e)}")
        except Exception as e:
            raise InvalidThemeError(f"Error loading theme '{theme_name}': {str(e)}")
            
    def apply_theme(self, component: Dict[str, Any], theme_name: str) -> Dict[str, Any]:
        """
        Apply a theme to a component.
        
        Args:
            component: Component dictionary to apply theme to
            theme_name: Name of the theme to apply
            
        Returns:
            Component with theme applied
            
        Raises:
            ThemeNotFoundError: If theme is not found
            ValueError: If component is invalid
        """
        if not isinstance(component, dict):
            raise ValueError("Component must be a dictionary")
            
        theme = self.load_theme(theme_name)
        result = component.copy()
        
        # Apply theme properties
        if 'styles' in theme:
            if 'styles' not in result:
                result['styles'] = {}
            result['styles'].update(theme['styles'])
            
        if 'colors' in theme:
            if 'colors' not in result:
                result['colors'] = {}
            result['colors'].update(theme['colors'])
            
        if 'fonts' in theme:
            if 'fonts' not in result:
                result['fonts'] = {}
            result['fonts'].update(theme['fonts'])
            
        # Apply any other theme properties
        for key, value in theme.items():
            if key not in ['styles', 'colors', 'fonts']:
                result[key] = value
                
        # Set current theme
        self._current_theme = theme_name
        result['theme'] = theme_name
        
        return result
        
    def apply_theme_to_components(self, components: List[Dict[str, Any]], 
                                  theme_name: str) -> List[Dict[str, Any]]:
        """
        Apply a theme to multiple components.
        
        Args:
            components: List of components to apply theme to
            theme_name: Name of the theme to apply
            
        Returns:
            List of components with theme applied
            
        Raises:
            ValueError: If components is not a list
        """
        if not isinstance(components, list):
            raise ValueError("Components must be a list")
            
        return [self.apply_theme(comp, theme_name) for comp in components]
        
    def register_theme(self, theme_name: str, theme_data: Dict[str, Any]) -> None:
        """
        Register a custom theme.
        
        Args:
            theme_name: Name of the theme
            theme_data: Theme configuration dictionary
            
        Raises:
            ValueError: If theme_data is invalid
        """
        if not isinstance(theme_data, dict):
            raise ValueError("Theme data must be a dictionary")
            
        if not theme_name:
            raise ValueError("Theme name cannot be empty")
            
        self._custom_themes[theme_name] = theme_data.copy()
        
    def get_current_theme(self) -> Optional[str]:
        """
        Get the name of the currently applied theme.
        
        Returns:
            Name of current theme or None if no theme is applied
        """
        return self._current_theme
        
    def list_available_themes(self) -> List[str]:
        """
        List all available themes.
        
        Returns:
            List of available theme names
        """
        themes = list(self._custom_themes.keys())
        
        # Add themes from directory
        if os.path.exists(self.theme_directory):
            for file in os.listdir(self.theme_directory):
                if file.endswith('.json') or file.endswith('.theme'):
                    theme_name = file.rsplit('.', 1)[0]
                    if theme_name not in themes:
                        themes.append(theme_name)
                        
        return sorted(themes)
        
    def validate_theme(self, theme_data: Dict[str, Any]) -> bool:
        """
        Validate theme data structure.
        
        Args:
            theme_data: Theme configuration to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(theme_data, dict):
            return False
            
        # Check for at least one valid theme section
        valid_sections = ['styles', 'colors', 'fonts', 'properties']
        has_valid_section = any(key in theme_data for key in valid_sections)
        
        return has_valid_section or len(theme_data) > 0
        
    def merge_themes(self, base_theme: str, override_theme: str) -> Dict[str, Any]:
        """
        Merge two themes, with override_theme taking precedence.
        
        Args:
            base_theme: Name of base theme
            override_theme: Name of override theme
            
        Returns:
            Merged theme configuration
        """
        base = self.load_theme(base_theme)
        override = self.load_theme(override_theme)
        
        # Deep merge
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key].update(value)
            else:
                result[key] = value
                
        return result
        
    def create_theme_variant(self, base_theme: str, variant_name: str, 
                            modifications: Dict[str, Any]) -> None:
        """
        Create a theme variant based on an existing theme.
        
        Args:
            base_theme: Name of base theme
            variant_name: Name for the new variant
            modifications: Modifications to apply to base theme
        """
        base = self.load_theme(base_theme)
        variant = base.copy()
        
        # Apply modifications
        for key, value in modifications.items():
            if key in variant and isinstance(variant[key], dict) and isinstance(value, dict):
                variant[key].update(value)
            else:
                variant[key] = value
                
        self.register_theme(variant_name, variant)
        
    def save_theme(self, theme_name: str, theme_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Save a theme to file.
        
        Args:
            theme_name: Name of the theme
            theme_data: Optional theme data (uses registered theme if not provided)
            
        Raises:
            ValueError: If theme_data is invalid
            ThemeNotFoundError: If theme not found and no data provided
        """
        if theme_data is None:
            if theme_name in self._custom_themes:
                theme_data = self._custom_themes[theme_name]
            else:
                raise ThemeNotFoundError(f"Theme '{theme_name}' not found")
                
        if not self.validate_theme(theme_data):
            raise ValueError("Invalid theme data")
            
        # Create directory if it doesn't exist
        os.makedirs(self.theme_directory, exist_ok=True)
        
        theme_path = os.path.join(self.theme_directory, f"{theme_name}.json")
        
        with open(theme_path, 'w') as f:
            json.dump(theme_data, f, indent=2)
            
    def remove_theme(self, theme_name: str) -> None:
        """
        Remove a theme.
        
        Args:
            theme_name: Name of the theme to remove
        """
        # Remove from custom themes
        if theme_name in self._custom_themes:
            del self._custom_themes[theme_name]
            
        # Remove from cache
        if theme_name in self._themes_cache:
            del self._themes_cache[theme_name]
            
        # Try to remove file
        theme_path = os.path.join(self.theme_directory, f"{theme_name}.json")
        if os.path.exists(theme_path):
            os.remove(theme_path)
            
        theme_path = os.path.join(self.theme_directory, f"{theme_name}.theme")
        if os.path.exists(theme_path):
            os.remove(theme_path)
            
        # Clear current theme if it was removed
        if self._current_theme == theme_name:
            self._current_theme = None


# Default instance for convenience
default_applier = ThemeApplier()


def apply_theme(component: Dict[str, Any], theme_name: str) -> Dict[str, Any]:
    """
    Convenience function to apply theme using default applier.
    
    Args:
        component: Component to apply theme to
        theme_name: Name of the theme
        
    Returns:
        Component with theme applied
    """
    return default_applier.apply_theme(component, theme_name)


def load_theme(theme_name: str) -> Dict[str, Any]:
    """
    Convenience function to load theme using default applier.
    
    Args:
        theme_name: Name of the theme
        
    Returns:
        Theme configuration dictionary
    """
    return default_applier.load_theme(theme_name)


def register_theme(theme_name: str, theme_data: Dict[str, Any]) -> None:
    """
    Convenience function to register theme using default applier.
    
    Args:
        theme_name: Name of the theme
        theme_data: Theme configuration
    """
    default_applier.register_theme(theme_name, theme_data)
