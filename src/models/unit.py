```python
from typing import List
from sqlalchemy import Column, Integer, String, ForeignKey

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UIElement(Base):
    __tablename__ = 'ui_element'
    id = Column(Integer, primary_key=True)
    name = Column(String)

    # Define relationships with other tables if needed

class UIProtocol(Base):
    __tablename__ = 'ui_protocol'
    elements = Column(Integer, ForeignKey('ui_element.id'))

    def __init__(self, elements: List[int]):
        self.elements = elements

    def __repr__(self):
        return f"<UIProtocol(elements={self.elements})>"

if __name__ == '__main__':
    # Example usage and creation of tables
    Base.metadata.create_all(bind=None)
```
