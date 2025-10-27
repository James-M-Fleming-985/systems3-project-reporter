class ContentInserter:
    """Handles content insertion operations with validation and error handling."""
    
    def __init__(self):
        """Initialize the ContentInserter."""
        self._content_store = {}
        self._id_counter = 1
    
    def insert_content(self, content, metadata=None):
        """
        Insert content with optional metadata.
        
        Args:
            content: The content to insert (must be non-empty string)
            metadata: Optional dictionary of metadata
            
        Returns:
            int: The ID of the inserted content
            
        Raises:
            ValueError: If content is invalid
            TypeError: If metadata is not a dictionary
        """
        if not isinstance(content, str):
            raise TypeError("Content must be a string")
        
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("Metadata must be a dictionary")
        
        content_id = self._id_counter
        self._content_store[content_id] = {
            'content': content.strip(),
            'metadata': metadata or {}
        }
        self._id_counter += 1
        
        return content_id
    
    def get_content(self, content_id):
        """
        Retrieve content by ID.
        
        Args:
            content_id: The ID of the content to retrieve
            
        Returns:
            dict: Content and metadata
            
        Raises:
            KeyError: If content_id not found
            TypeError: If content_id is not an integer
        """
        if not isinstance(content_id, int):
            raise TypeError("Content ID must be an integer")
        
        if content_id not in self._content_store:
            raise KeyError(f"Content with ID {content_id} not found")
        
        return self._content_store[content_id].copy()
    
    def update_content(self, content_id, new_content=None, new_metadata=None):
        """
        Update existing content and/or metadata.
        
        Args:
            content_id: The ID of the content to update
            new_content: New content string (optional)
            new_metadata: New metadata dictionary (optional)
            
        Returns:
            bool: True if update successful
            
        Raises:
            KeyError: If content_id not found
            ValueError: If new_content is empty
            TypeError: If types are incorrect
        """
        if not isinstance(content_id, int):
            raise TypeError("Content ID must be an integer")
        
        if content_id not in self._content_store:
            raise KeyError(f"Content with ID {content_id} not found")
        
        if new_content is not None:
            if not isinstance(new_content, str):
                raise TypeError("Content must be a string")
            if not new_content or not new_content.strip():
                raise ValueError("Content cannot be empty")
            self._content_store[content_id]['content'] = new_content.strip()
        
        if new_metadata is not None:
            if not isinstance(new_metadata, dict):
                raise TypeError("Metadata must be a dictionary")
            self._content_store[content_id]['metadata'] = new_metadata
        
        return True
    
    def delete_content(self, content_id):
        """
        Delete content by ID.
        
        Args:
            content_id: The ID of the content to delete
            
        Returns:
            bool: True if deletion successful
            
        Raises:
            KeyError: If content_id not found
            TypeError: If content_id is not an integer
        """
        if not isinstance(content_id, int):
            raise TypeError("Content ID must be an integer")
        
        if content_id not in self._content_store:
            raise KeyError(f"Content with ID {content_id} not found")
        
        del self._content_store[content_id]
        return True
    
    def list_content_ids(self):
        """
        Get a list of all content IDs.
        
        Returns:
            list: List of content IDs
        """
        return sorted(list(self._content_store.keys()))
    
    def search_content(self, search_term):
        """
        Search for content containing the search term.
        
        Args:
            search_term: The term to search for
            
        Returns:
            list: List of content IDs matching the search
            
        Raises:
            TypeError: If search_term is not a string
        """
        if not isinstance(search_term, str):
            raise TypeError("Search term must be a string")
        
        if not search_term:
            return []
        
        search_term_lower = search_term.lower()
        matching_ids = []
        
        for content_id, data in self._content_store.items():
            if search_term_lower in data['content'].lower():
                matching_ids.append(content_id)
        
        return sorted(matching_ids)
    
    def clear_all_content(self):
        """
        Clear all stored content.
        
        Returns:
            bool: True if successful
        """
        self._content_store.clear()
        self._id_counter = 1
        return True
    
    def get_content_count(self):
        """
        Get the total number of stored content items.
        
        Returns:
            int: Number of content items
        """
        return len(self._content_store)
    
    def bulk_insert(self, content_list):
        """
        Insert multiple content items at once.
        
        Args:
            content_list: List of content items (strings or tuples of (content, metadata))
            
        Returns:
            list: List of content IDs for inserted items
            
        Raises:
            TypeError: If content_list is not a list
            ValueError: If any content item is invalid
        """
        if not isinstance(content_list, list):
            raise TypeError("Content list must be a list")
        
        if not content_list:
            return []
        
        inserted_ids = []
        
        for item in content_list:
            if isinstance(item, str):
                content_id = self.insert_content(item)
                inserted_ids.append(content_id)
            elif isinstance(item, tuple) and len(item) == 2:
                content, metadata = item
                content_id = self.insert_content(content, metadata)
                inserted_ids.append(content_id)
            else:
                raise ValueError("Each item must be a string or tuple of (content, metadata)")
        
        return inserted_ids
