import json
import boto3
from datetime import datetime, timezone

# AWS clients
ec2_client    = boto3.client('ec2')
rds_client    = boto3.client('rds')
lambda_client = boto3.client('lambda')
dynamodb      = boto3.resource('dynamodb')
table         = dynamodb.Table('idle_alerts')

# Threshold in hours
IDLE_THRESHOLD_HOURS = 3

def lambda_handler(event, context):
    print("Idle Checker started:", datetime.now(timezone.utc).isoformat())

    try:
        check_ec2_instances()
        check_rds_instances()

        return {
            'statusCode': 200,
            'body': 'Idle check complete'
        }

    except Exception as e:
        print("ERROR:", str(e))
        raise e


def check_ec2_instances():
    """Check all running EC2 instances"""
    print("Checking EC2 instances...")

    response = ec2_client.describe_instances(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id   = instance['InstanceId']
            instance_type = instance['InstanceType']
            launch_time   = instance['LaunchTime']

            # Calculate how long it has been running
            now             = datetime.now(timezone.utc)
            hours_running   = (now - launch_time).total_seconds() / 3600

            print(f"EC2 {instance_id} running for {hours_running:.1f} hours")

            # If running more than threshold
            if hours_running >= IDLE_THRESHOLD_HOURS:
                if not already_alerted(instance_id, hours_running):
                    print(f"IDLE ALERT: EC2 {instance_id} running for {hours_running:.1f} hrs")
                    trigger_notifier(
                        service_id     = instance_id,
                        service_type   = 'EC2',
                        instance_type  = instance_type,
                        hours_running  = round(hours_running, 1)
                    )
                    save_alert(instance_id, hours_running)


def check_rds_instances():
    """Check all running RDS instances"""
    print("Checking RDS instances...")

    response = rds_client.describe_db_instances()

    for db in response['DBInstances']:
        db_id     = db['DBInstanceIdentifier']
        db_class  = db['DBInstanceClass']
        status    = db['DBInstanceStatus']

        # Only check available (running) instances
        if status != 'available':
            continue

        # RDS doesn't give launch time directly
        # Use instance create time as approximation
        create_time   = db['InstanceCreateTime']
        now           = datetime.now(timezone.utc)
        hours_running = (now - create_time).total_seconds() / 3600

        print(f"RDS {db_id} running for {hours_running:.1f} hours")

        if hours_running >= IDLE_THRESHOLD_HOURS:
            if not already_alerted(db_id, hours_running):
                print(f"IDLE ALERT: RDS {db_id} running for {hours_running:.1f} hrs")
                trigger_notifier(
                    service_id    = db_id,
                    service_type  = 'RDS',
                    instance_type = db_class,
                    hours_running = round(hours_running, 1)
                )
                save_alert(db_id, hours_running)


def already_alerted(service_id, hours_running):
    """Check if we already sent alert for this service at this hour mark"""
    try:
        hour_mark = str(int(hours_running // IDLE_THRESHOLD_HOURS) * IDLE_THRESHOLD_HOURS)

        response = table.get_item(
            Key={
                'service_id': service_id,
                'hour_mark':  hour_mark
            }
        )
        exists = 'Item' in response
        if exists:
            print(f"Already alerted {service_id} at {hour_mark}hr mark — skipping")
        return exists

    except Exception as e:
        print("Could not check alert history:", str(e))
        return False


def save_alert(service_id, hours_running):
    """Save alert record so we dont spam"""
    try:
        hour_mark = str(int(hours_running // IDLE_THRESHOLD_HOURS) * IDLE_THRESHOLD_HOURS)

        table.put_item(Item={
            'service_id': service_id,
            'hour_mark':  hour_mark,
            'alerted_at': datetime.now(timezone.utc).isoformat()
        })
        print(f"Alert record saved for {service_id} at {hour_mark}hr mark")

    except Exception as e:
        print("Could not save alert record:", str(e))


def trigger_notifier(service_id, service_type, instance_type, hours_running):
    """Call Lambda #3 to send idle alert email"""
    try:
        payload = {
            'alert_type':   'IDLE',
            'service_id':   service_id,
            'service_type': service_type,
            'instance_type': instance_type,
            'hours_running': hours_running
        }

        lambda_client.invoke(
            FunctionName   = 'aws-cost-guard-notifier',
            InvocationType = 'Event',
            Payload        = json.dumps(payload)
        )
        print(f"Notifier triggered for idle service: {service_id}")

    except Exception as e:
        print("Could not trigger notifier:", str(e))
