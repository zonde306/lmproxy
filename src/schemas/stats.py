import abc

ValueType = int | str | float | None | dict | list | tuple

class Stats(abc.ABC):
    @abc.abstractmethod
    async def value(self, key : str) -> ValueType:
        """
        Get the value of a key. If the key does not exist, return None.
        """
        ...
    
    @abc.abstractmethod
    async def set(self, key : str, value : ValueType) -> None:
        """
        Set the value of a key. If the key already exists, update it.
        """
        ...
    
    @abc.abstractmethod
    async def incr(self, key : str, value : int = 1) -> None:
        """
        Increment the value of a key. If the key does not exist, create it with the value 0 and then increment it.
        """
        ...
    
    @abc.abstractmethod
    async def decr(self, key : str, value : int = 1) -> None:
        """
        Decrement the value of a key. If the key does not exist, create it with the value 0 and then decrement it.
        """
        ...
    
    @abc.abstractmethod
    async def has(self, key : str) -> bool:
        """
        Check if a key exists.
        """
        ...
    
    @abc.abstractmethod
    async def add(self, key : str, value : ValueType) -> None:
        """
        Add a key to list if it does not exist. If the key exists, raise an exception.
        """
        ...
    
    @abc.abstractmethod
    async def remove(self, key : str, value : ValueType) -> None:
        """
        Delete a key from list.
        """
        ...
    
    @abc.abstractmethod
    async def contains(self, key : str, value : ValueType) -> bool:
        """
        Check if a key exists in list or dict.
        """
        ...
    
    @abc.abstractmethod
    async def clear(self, key : str) -> None:
        """
        Clear elements with list.
        """
        ...
