import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Union
import time


class FileParseError(Exception):
    """Custom exception for file parsing errors."""
    pass


class BaseReader:
    """Base class for file readers."""
    
    def __init__(self, file_path: Union[str, Path]):
        """Initialize reader with file path.
        
        Args:
            file_path: Path to the file to read
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
    
    def read(self) -> Dict[str, Any]:
        """Read and parse the file.
        
        Returns:
            Parsed file content as dictionary
            
        Raises:
            FileParseError: If file cannot be parsed
        """
        raise NotImplementedError("Subclasses must implement read method")


class YAMLReader(BaseReader):
    """Reader for YAML files."""
    
    def read(self) -> Dict[str, Any]:
        """Read and parse YAML file.
        
        Returns:
            Parsed YAML content as dictionary
            
        Raises:
            FileParseError: If YAML is malformed
        """
        try:
            # Try UTF-8 first
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except UnicodeDecodeError:
            # Fall back to UTF-16
            with open(self.file_path, 'r', encoding='utf-16') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            # Extract line number from error if available
            line_no = None
            if hasattr(e, 'problem_mark'):
                line_no = e.problem_mark.line + 1
            
            if line_no:
                raise FileParseError(f"YAML parse error at line {line_no}")
            else:
                raise FileParseError(f"YAML parse error: {str(e)}")
        except Exception as e:
            raise FileParseError(f"Error reading YAML file: {str(e)}")


class XMLReader(BaseReader):
    """Reader for XML files."""
    
    def read(self) -> Dict[str, Any]:
        """Read and parse XML file.
        
        Returns:
            Parsed XML content as dictionary
            
        Raises:
            FileParseError: If XML is malformed
        """
        try:
            # Try UTF-8 first
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Fall back to UTF-16
                with open(self.file_path, 'r', encoding='utf-16') as f:
                    content = f.read()
            
            root = ET.fromstring(content)
            return self._xml_to_dict(root)
        except ET.ParseError as e:
            raise FileParseError(f"XML parse error: {str(e)}")
        except Exception as e:
            raise FileParseError(f"Error reading XML file: {str(e)}")
    
    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary.
        
        Args:
            element: XML element to convert
            
        Returns:
            Dictionary representation of XML element
        """
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0 and not element.attrib:
                # If no children and no attributes, return just the text
                return element.text.strip()
            else:
                result['#text'] = element.text.strip()
        
        # Add children
        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                # If tag already exists, convert to list
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        # If only text content, return it directly
        if len(result) == 1 and '#text' in result:
            return result['#text']
        
        # If empty element with no attributes
        if not result:
            return None
            
        return result


class FileReaderFactory:
    """Factory class for creating appropriate file readers."""
    
    @staticmethod
    def create_reader(file_path: Union[str, Path]) -> BaseReader:
        """Create appropriate reader based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Appropriate reader instance
            
        Raises:
            ValueError: If file extension is not supported
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension in ['.yml', '.yaml']:
            return YAMLReader(file_path)
        elif extension == '.xml':
            return XMLReader(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {extension}")
