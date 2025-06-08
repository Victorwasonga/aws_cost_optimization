import boto3
import datetime
from statistics import mean

REGION = "us-east-1"
DAYS = 14
THRESHOLDS = {
    "cpu": 40,           # % CPU threshold for utilization
    "network": 1_000_000,  # ~1MB/s network throughput in bytes
    "disk_ops": 100      # ops/sec
}

ec2 = boto3.client('ec2', region_name=REGION)
cloudwatch = boto3.client('cloudwatch', region_name=REGION)
rds = boto3.client('rds', region_name=REGION)

end = datetime.datetime.utcnow()
start = end - datetime.timedelta(days=DAYS)

def get_metric(resource_id, metric_name, namespace, stat="Average", unit=None, dimension_name="InstanceId"):
    dims = [{"Name": dimension_name, "Value": resource_id}]
    params = dict(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dims,
        StartTime=start,
        EndTime=end,
        Period=86400,
        Statistics=[stat],
    )
    if unit:
        params['Unit'] = unit

    response = cloudwatch.get_metric_statistics(**params)
    datapoints = response.get('Datapoints', [])
    return [dp[stat] for dp in sorted(datapoints, key=lambda x: x['Timestamp'])]

def get_rds_metric(db_instance_id, metric_name, stat="Average", unit=None):
    return get_metric(db_instance_id, metric_name, "AWS/RDS", stat, unit, dimension_name="DBInstanceIdentifier")

print("\n📊 AWS Cost Optimization Report\n" + "-"*35)

# === EC2 Instances ===
print("\n🔹 EC2 Instances Rightsizing and Utilization\n" + "-"*35)
instances = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])
for reservation in instances['Reservations']:
    for instance in reservation['Instances']:
        iid = instance['InstanceId']
        itype = instance['InstanceType']
        name = next((t['Value'] for t in instance.get('Tags', []) if t['Key'] == 'Name'), 'N/A')

        cpu = mean(get_metric(iid, 'CPUUtilization', 'AWS/EC2', unit='Percent') or [0])
        net_in = mean(get_metric(iid, 'NetworkIn', 'AWS/EC2', unit='Bytes') or [0])
        net_out = mean(get_metric(iid, 'NetworkOut', 'AWS/EC2', unit='Bytes') or [0])
        disk_ops = mean(get_metric(iid, 'DiskReadOps', 'AWS/EC2', unit='Count') or [0]) + \
                   mean(get_metric(iid, 'DiskWriteOps', 'AWS/EC2', unit='Count') or [0])

        net_total = net_in + net_out

        status = "✅ Utilized"
        notes = []

        if cpu < THRESHOLDS['cpu'] and net_total < THRESHOLDS['network'] and disk_ops < THRESHOLDS['disk_ops']:
            status = "🔴 Overprovisioned"
        else:
            if cpu < THRESHOLDS['cpu']:
                notes.append("Low CPU")
            if net_total < THRESHOLDS['network']:
                notes.append("Low Network")
            if disk_ops < THRESHOLDS['disk_ops']:
                notes.append("Low Disk Ops")
            if notes:
                status = "⚠️ Review: " + ", ".join(notes)

        print(f"Instance: {iid} ({name})")
        print(f"Type: {itype}")
        print(f" - Avg CPU: {cpu:.2f}%")
        print(f" - Avg Network: {net_total:.2f} Bytes/s")
        print(f" - Avg Disk Ops: {disk_ops:.2f} ops/s")
        print(f" → {status}\n")

# === RDS Instances ===
print("\n🔹 RDS Instances Rightsizing and Utilization\n" + "-"*35)
dbs = rds.describe_db_instances()
for db in dbs['DBInstances']:
    dbid = db['DBInstanceIdentifier']
    dbtype = db['DBInstanceClass']

    cpu = mean(get_rds_metric(dbid, 'CPUUtilization', unit='Percent') or [0])
    free_storage = mean(get_rds_metric(dbid, 'FreeStorageSpace', unit='Bytes') or [0])
    storage_allocated = db.get('AllocatedStorage', 0) * 1024**3  # GB to Bytes

    status = "✅ Utilized"
    notes = []

    if cpu < THRESHOLDS['cpu']:
        notes.append("Low CPU")
    if free_storage > 0.8 * storage_allocated:
        notes.append("Underutilized Storage")
    elif free_storage < 0.1 * storage_allocated:
        notes.append("Storage Nearly Full")

    if notes:
        status = "⚠️ Review: " + ", ".join(notes)

    print(f"DB Instance: {dbid}")
    print(f"Type: {dbtype}")
    print(f" - Avg CPU: {cpu:.2f}%")
    print(f" - Free Storage: {free_storage / 1024**3:.2f} GB")
    print(f" - Allocated Storage: {storage_allocated / 1024**3:.2f} GB")
    print(f" → {status}\n")

# === Unused Resources Audit ===
print("🔍 Unused AWS Resources Audit\n" + "-"*35)

# Unattached EBS Volumes
volumes = ec2.describe_volumes(Filters=[{'Name':'status','Values':['available']}])
print(f"📦 Unattached EBS Volumes: {len(volumes['Volumes'])}")
for v in volumes['Volumes']:
    print(f" - {v['VolumeId']}")

# Unused Snapshots (snapshots not attached to any volume)
snapshots = ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']
attached_volume_ids = {v['VolumeId'] for v in ec2.describe_volumes()['Volumes'] if v['State'] == 'in-use'}

unused_snapshots = []
for snap in snapshots:
    if snap.get('VolumeId') not in attached_volume_ids:
        unused_snapshots.append(snap['SnapshotId'])

print(f"\n📸 Unused Snapshots: {len(unused_snapshots)}")
for snap_id in unused_snapshots:
    print(f" - {snap_id}")

# Unassociated Elastic IPs
addresses = ec2.describe_addresses()
unassociated = [a for a in addresses['Addresses'] if 'InstanceId' not in a and 'NetworkInterfaceId' not in a]
print(f"\n🌐 Unassociated Elastic IPs: {len(unassociated)}")
for ip in unassociated:
    print(f" - {ip['PublicIp']}")

print("\nReport complete.\n")
