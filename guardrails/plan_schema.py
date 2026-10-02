from pydantic import BaseModel, Field, field_validator

class ResourceSpec(BaseModel):
    name: str
    primary_key: str | None = None

class IngestionPlan(BaseModel):
    base_url: str
    data_selector: str = "results"
    next_url_path: str | None = "next"
    resources: list[ResourceSpec] = Field(min_length=1, max_length=10)
    
    @field_validator("base_url")
    @classmethod
    
    def _http(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        return v