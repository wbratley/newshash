from datetime import datetime
from pydantic import BaseModel


class Source(BaseModel):
    outlet: str
    lean: str
    headline: str
    url: str
    published: str | None = None
    summary: str = ""
    article_id: str = ""


class OutletAnalysis(BaseModel):
    outlet: str
    lean: str
    angle: str
    bias_notes: str
    articles: list[Source]


class Cluster(BaseModel):
    id: str
    neutral_headline: str
    unbiased_summary: str
    outlets: list[OutletAnalysis]


class NewsResponse(BaseModel):
    generated_at: datetime
    cluster_count: int
    clusters: list[Cluster]
