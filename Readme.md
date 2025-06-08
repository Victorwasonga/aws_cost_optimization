# AWS Cost Optimization Report Script

This Python script helps identify cost-saving opportunities in your AWS environment by analyzing resource utilization and flagging potential overprovisioning and unused resources.

---

## Features

- **EC2 Instances Rightsizing**  
  Analyzes average CPU, network, and disk I/O utilization over the last 14 days and flags instances as:
  - Overprovisioned (low utilization across metrics)
  - Utilized
  - Needs Review (e.g., only one metric is active)

- **RDS Instances Rightsizing**  
  Checks average CPU utilization and storage usage, flagging underutilized or nearly full databases for review.

- **Unused AWS Resources Audit**  
  Identifies unattached EBS volumes, unused EBS snapshots, and unassociated Elastic IP addresses to help reduce unnecessary costs.

---

## Prerequisites

- Python 3.x
- `boto3` library installed  
  Install with:  
  ```bash
  pip install boto3
