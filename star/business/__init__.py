"""Offline STAR Business OS research support (no commercial actions).

Importing this package does not invoke a model, use the network, or alter files.
"""
from .opportunities import (
    IllustrativeUnitEconomics,
    Opportunity,
    OpportunityScorecard,
    load_catalog,
)

__all__ = ["IllustrativeUnitEconomics", "Opportunity", "OpportunityScorecard", "load_catalog"]
