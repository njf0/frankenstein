import json
from typing import List

from pydantic import BaseModel, field_validator


# ToolCall model with generic structure
class ToolCall(BaseModel):
    name: str  # Tool name
    arguments: str  # Arguments as raw string (assumed to be JSON-encoded)

    @field_validator('arguments')
    def validate_arguments(cls, value):
        try:
            # Try to parse the arguments to ensure they are valid JSON
            json.loads(value)
        except json.JSONDecodeError:
            raise ValueError('Invalid JSON format for arguments')
        return value

    class Config:
        extra = 'forbid'  # Ensure no extra properties


# Final schema that includes a list of tool calls
class FranklinSchema(BaseModel):
    tool_calls: List[ToolCall]

    class Config:
        extra = 'forbid'  # Ensure no extra properties for the entire schema


if __name__ == '__main__':
    # Example usage
    example_tool_call = ToolCall(name='example_tool', arguments='{"key": "value"}')
    example_schema = FranklinSchema(tool_calls=[example_tool_call])
    print(example_schema.model_dump_json(indent=2))
