import json

class Engine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = False
        return cls._instance

    def __init__(self) -> None:
        if self._lock:
            return
        self._lock = True
        self.index = {}

    def load_index(self, path: str) -> None:
        """Load the index from a file."""
        try: 
            with open(path, 'r') as f:
                self.index = json.load(f)
        except FileNotFoundError:
            print(f"File not found: {path}")
        except json.JSONDecodeError:
            print(f"Invalid JSON in file: {path}")