import json
import boto3
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Attr

# AWS clients
dynamodb = boto3.resource('dynamodb')
table    = dynamodb.Table('shutdown_events')
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    print("Zombie Checker started:", datetime.now(timezone.utc).isoformat())

    try:
        # Scan DynamoDB for all incomplete shutdowns
        response = table.scan(
            FilterExpression=Attr('shutdown_complete').eq(False)
        )
        items = response.get('Items', [])
        print(f"Found {len(items)} incomplete shutdowns")

        zombie_count = 0

        for item in items:
            service_id   = item.get('service_id')
            service_type = item.get('service_type')
            start_time   = item.get('start_time')
            region       = item.get('region')

            if not start_time:
                continue

            # Calculate how long it has been stopping
            start        = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            now          = datetime.now(timezone.utc)
            minutes_elapsed = (now - start).total_seconds() / 60

            print(f"{service_type} {service_id} has been stopping for {minutes_elapsed:.1f} minutes")

            # If stopping for more than 10 minutes → ZOMBIE!
            if minutes_elapsed > 10:
                print(f"ZOMBIE DETECTED: {service_type} {service_id}")
                zombie_count += 1

                # Update DynamoDB — mark as zombie
                table.update_item(
                    Key={
                        'service_id': service_id,
                        'event_time': item.get('event_time')
                    },
                    UpdateExpression='SET #s = :zombie, zombie = :true',
                    ExpressionAttributeNames={'#s': 'status'},
                    ExpressionAttributeValues={
                        ':zombie': 'ZOMBIE',
                        ':true':    True
                    }
                )

                # Trigger Lambda #3 to send alert email
                trigger_notifier(service_id, service_type, region, minutes_elapsed)

        print(f"Zombie check complete. {zombie_count} zombies found.")
        return {
            'statusCode': 200,
            'body': f'{zombie_count} zombies detected'
        }

    except Exception as e:
        print("ERROR:", str(e))
        raise e


def trigger_notifier(service_id, service_type, region, minutes_elapsed):
    
    try:
        payload = {
            'alert_type':      'ZOMBIE',
            'service_id':      service_id,
            'service_type':    service_type,
            'region':          region,
            'minutes_elapsed': round(minutes_elapsed, 1)
        }

        lambda_client.invoke(
            FunctionName='aws-cost-guard-notifier',
            InvocationType='Event',  # async call
            Payload=json.dumps(payload)
        )
        print(f"Notifier triggered for zombie: {service_id}")

    except Exception as e:
        print("Could not trigger notifier:", str(e))
