"""Global tool pool shared across all worker sub-graphs.

Holds external-service clients (Salesforce, OpenAI, pgvector) and registry
loaders (canonical + destination schemas). Workers import from here; nothing
here imports from a worker.
"""
