import sys
from typing import List, Dict, Any, Optional, Tuple
import json
import os


class TerminalUI:
    """Terminal User Interface for handling user interactions."""
    
    def __init__(self):
        """Initialize the Terminal UI."""
        self.commands = {
            'help': self._show_help,
            'list': self._list_items,
            'add': self._add_item,
            'remove': self._remove_item,
            'view': self._view_item,
            'exit': self._exit
        }
        self.data = []
        self.running = True
    
    def display_menu(self):
        """Display the main menu options."""
        print("\n=== Terminal UI Menu ===")
        print("1. help - Show available commands")
        print("2. list - List all items")
        print("3. add <item> - Add a new item")
        print("4. remove <id> - Remove an item by ID")
        print("5. view <id> - View details of an item")
        print("6. exit - Exit the application")
        print("========================\n")
    
    def get_user_input(self) -> str:
        """Get input from the user."""
        return input("Enter command: ").strip()
    
    def process_command(self, command: str) -> Dict[str, Any]:
        """Process user command and return result."""
        if not command:
            return {'status': 'error', 'message': 'Empty command'}
        
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd not in self.commands:
            return {'status': 'error', 'message': f'Unknown command: {cmd}'}
        
        try:
            return self.commands[cmd](args)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def display_result(self, result: Dict[str, Any]):
        """Display the result of a command execution."""
        if result['status'] == 'success':
            print(f"Success: {result.get('message', 'Operation completed')}")
            if 'data' in result:
                self._display_data(result['data'])
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")
    
    def run(self):
        """Main loop for the terminal UI."""
        self.display_menu()
        while self.running:
            try:
                user_input = self.get_user_input()
                result = self.process_command(user_input)
                self.display_result(result)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
    
    def _show_help(self, args: str) -> Dict[str, Any]:
        """Show help information."""
        help_text = """
Available Commands:
- help: Show this help message
- list: Display all items
- add <item>: Add a new item
- remove <id>: Remove item by ID
- view <id>: View details of a specific item
- exit: Exit the application
        """
        return {'status': 'success', 'message': help_text}
    
    def _list_items(self, args: str) -> Dict[str, Any]:
        """List all items."""
        if not self.data:
            return {'status': 'success', 'message': 'No items found', 'data': []}
        return {'status': 'success', 'message': f'Found {len(self.data)} items', 'data': self.data}
    
    def _add_item(self, args: str) -> Dict[str, Any]:
        """Add a new item."""
        if not args:
            return {'status': 'error', 'message': 'Item name required'}
        
        item_id = len(self.data) + 1
        new_item = {'id': item_id, 'name': args}
        self.data.append(new_item)
        return {'status': 'success', 'message': f'Item added with ID: {item_id}'}
    
    def _remove_item(self, args: str) -> Dict[str, Any]:
        """Remove an item by ID."""
        if not args:
            return {'status': 'error', 'message': 'Item ID required'}
        
        try:
            item_id = int(args)
        except ValueError:
            return {'status': 'error', 'message': 'Invalid ID format'}
        
        for i, item in enumerate(self.data):
            if item['id'] == item_id:
                removed = self.data.pop(i)
                return {'status': 'success', 'message': f'Removed item: {removed["name"]}'}
        
        return {'status': 'error', 'message': f'Item with ID {item_id} not found'}
    
    def _view_item(self, args: str) -> Dict[str, Any]:
        """View details of a specific item."""
        if not args:
            return {'status': 'error', 'message': 'Item ID required'}
        
        try:
            item_id = int(args)
        except ValueError:
            return {'status': 'error', 'message': 'Invalid ID format'}
        
        for item in self.data:
            if item['id'] == item_id:
                return {'status': 'success', 'message': 'Item found', 'data': item}
        
        return {'status': 'error', 'message': f'Item with ID {item_id} not found'}
    
    def _exit(self, args: str) -> Dict[str, Any]:
        """Exit the application."""
        self.running = False
        return {'status': 'success', 'message': 'Goodbye!'}
    
    def _display_data(self, data):
        """Display data in a formatted way."""
        if isinstance(data, list):
            for item in data:
                print(f"ID: {item['id']}, Name: {item['name']}")
        elif isinstance(data, dict):
            for key, value in data.items():
                print(f"{key}: {value}")
        else:
            print(data)


def validate_input(input_data: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate input data.
    
    Args:
        input_data: Data to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if input_data is None:
        return False, "Input cannot be None"
    
    if isinstance(input_data, str):
        if not input_data.strip():
            return False, "Input cannot be empty"
        return True, None
    
    if isinstance(input_data, dict):
        if not input_data:
            return False, "Input dictionary cannot be empty"
        return True, None
    
    if isinstance(input_data, list):
        return True, None
    
    return True, None


def handle_error(error: Exception) -> Dict[str, Any]:
    """
    Handle errors and return appropriate error response.
    
    Args:
        error: Exception to handle
    
    Returns:
        Error response dictionary
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    if isinstance(error, ValueError):
        return {'status': 'error', 'message': f'Value error: {error_message}'}
    elif isinstance(error, KeyError):
        return {'status': 'error', 'message': f'Key error: {error_message}'}
    elif isinstance(error, TypeError):
        return {'status': 'error', 'message': f'Type error: {error_message}'}
    else:
        return {'status': 'error', 'message': f'{error_type}: {error_message}'}


def main():
    """Main entry point for the terminal UI application."""
    ui = TerminalUI()
    ui.run()


if __name__ == "__main__":
    main()
