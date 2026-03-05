import json
import boto3
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

# AWS clients
dynamodb     = boto3.resource('dynamodb')
table        = dynamodb.Table('shutdown_events')
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    print("Event received:", json.dumps(event))

    try:
        # Extract info from EventBridge event
        service_type = detect_service_type(event)
        service_id   = get_service_id(event, service_type)
        status       = get_status(event, service_type)
        region       = event.get('region', 'unknown')
        event_time   = event.get('time', datetime.now(timezone.utc).isoformat())

        print(f"Service: {service_type} | ID: {service_id} | Status: {status}")

        # Build the record
        record = {
            'service_id':        service_id,
            'event_time':        event_time,
            'service_type':      service_type,
            'region':            region,
            'status':            status,
            'shutdown_complete': False
        }

        # If stopping — log start time
        if status in ['stopping', 'shutting-down']:
            record['start_time']        = event_time
            record['shutdown_complete'] = False
            table.put_item(Item=record)
            print("Stopping event logged in DynamoDB")

        # If stopped — calculate duration + send success email
        elif status in ['stopped', 'terminated']:
            record['end_time']          = event_time
            record['shutdown_complete'] = True
            record = calculate_duration(service_id, record, event_time)
            table.put_item(Item=record)
            print("Stopped event logged in DynamoDB")

            # Trigger Lambda #3 to send success email
            trigger_notifier(
                service_id       = service_id,
                service_type     = service_type,
                region           = region,
                duration_seconds = record.get('duration_seconds', 0)
            )

        return {
            'statusCode': 200,
            'body':       'Event logged successfully'
        }

    except Exception as e:
        print("ERROR:", str(e))
        raise e


def detect_service_type(event):
    source = event.get('source', '')
    if source == 'aws.ec2':
        return 'EC2'
    elif source == 'aws.rds':
        return 'RDS'
    elif source == 'aws.ecs':
        return 'ECS'
    return 'UNKNOWN'


def get_service_id(event, service_type):
    detail = event.get('detail', {})
    if service_type == 'EC2':
        return detail.get('instance-id', 'unknown')
    elif service_type == 'RDS':
        return detail.get('DbInstanceIdentifier', 'unknown')
    elif service_type == 'ECS':
        return detail.get('taskArn', 'unknown').split('/')[-1]
    return 'unknown'


def get_status(event, service_type):
    detail = event.get('detail', {})
    if service_type == 'EC2':
        return detail.get('state', 'unknown')
    elif service_type == 'RDS':
        return detail.get('EventID', 'unknown')
    elif service_type == 'ECS':
        return detail.get('lastStatus', 'unknown')
    return 'unknown'


def calculate_duration(service_id, record, event_time):
    """Find the matching stopping event and calculate duration"""
    try:
        response = table.query(
            KeyConditionExpression=Key('service_id').eq(service_id),
            ScanIndexForward=False,  # latest first
            Limit=5
        )
        items = response.get('Items', [])

        # Find the last stopping record
        for item in items:
            if not item.get('shutdown_complete', True):
                start    = datetime.fromisoformat(item['start_time'].replace('Z', '+00:00'))
                end      = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                duration = int((end - start).total_seconds())
                record['duration_seconds'] = duration
                print(f"Duration calculated: {duration} seconds")
                break

    except Exception as e:
        print("Could not calculate duration:", str(e))

    return record


def trigger_notifier(service_id, service_type, region, duration_seconds):
    """Call Lambda #3 to send success email"""
    try:
        payload = {
            'alert_type':       'SUCCESS',
            'service_id':       service_id,
            'service_type':     service_type,
            'region':           region,
            'duration_seconds': duration_seconds
        }

        lambda_client.invoke(
            FunctionName  = 'aws-cost-guard-notifier',
            InvocationType= 'Event',  # async call
            Payload       = json.dumps(payload)
        )
        print(f"Notifier triggered for successful stop: {service_id}")

    except Exception as e:
        print("Could not trigger notifier:", str(e))
