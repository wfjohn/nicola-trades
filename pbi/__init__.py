"""Power BI (Fabric semantic model) feed for pending redemptions.

Power BI is queried through the claude.ai PowerBI connector (DAX via ExecuteQuery). The queries live in
pbi/queries/*.dax; their saved results are loaded into data/trades.db by the scripts in this package.
See pbi/README.md.
"""
