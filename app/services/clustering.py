import logging
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.services.rss import RawStory

logger = logging.getLogger(__name__)


def cluster_stories(stories: list[RawStory]) -> list[list[RawStory]]:
    if not stories:
        return []

    titles = [s["title"] for s in stories]

    try:
        vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
        tfidf_matrix = vectorizer.fit_transform(titles)
        sim_matrix = cosine_similarity(tfidf_matrix)
    except Exception as exc:
        logger.warning("Clustering failed, returning singletons: %s", exc)
        return [[s] for s in stories]

    threshold = settings.cluster_similarity_threshold
    n = len(stories)

    # Build adjacency list
    graph: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= threshold:
                graph[i].append(j)
                graph[j].append(i)

    # Connected components via BFS
    visited = np.zeros(n, dtype=bool)
    clusters: list[list[RawStory]] = []

    for start in range(n):
        if visited[start]:
            continue
        component = []
        queue = [start]
        visited[start] = True
        while queue:
            node = queue.pop(0)
            component.append(stories[node])
            for neighbour in graph[node]:
                if not visited[neighbour]:
                    visited[neighbour] = True
                    queue.append(neighbour)
        clusters.append(component)

    # Sort clusters by size (largest first) so top stories appear first
    clusters.sort(key=lambda c: (len({s["outlet"] for s in c}), len(c)), reverse=True)
    logger.info("Produced %d clusters from %d stories", len(clusters), n)
    return clusters
