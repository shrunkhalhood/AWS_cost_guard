import json
import boto3
from datetime import datetime

# AWS clients
sns = boto3.client('sns', region_name='us-east-1')


SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:255260635688:aws-cost-guard-alerts'

def lambda_handler(event, context):
    print("Notifier triggered:", json.dumps(event))

    try:
        alert_type   = event.get('alert_type', 'UNKNOWN')

        if alert_type == 'ZOMBIE':
            send_zombie_alert(event)

        elif alert_type == 'SUCCESS':
            send_success_alert(event)

        return {
            'statusCode': 200,
            'body': 'Notification sent successfully'
        }

    except Exception as e:
        print("ERROR:", str(e))
        raise e


def send_zombie_alert(event):

    service_id      = event.get('service_id')
    service_type    = event.get('service_type')
    region          = event.get('region')
    minutes_elapsed = event.get('minutes_elapsed')

    subject = f"⚠️ AWS Cost Guard Alert — Zombie {service_type} Detected!"

    message = f"""
⚠️  ZOMBIE SERVICE DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service Type  : {service_type}
Service ID    : {service_id}
Region        : {region}
Stuck For     : {minutes_elapsed} minutes

This service has been in STOPPING state for over 10 minutes.
It may be stuck and still consuming your AWS credits!

ACTION REQUIRED:
→ Login to AWS Console
→ Check the service manually
→ Force stop or terminate if needed

━━━━━━━━━━━━━━━━━━━━━━━━━━━
AWS Cost Guard — Automated Alert
    """

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=subject,
        Message=message
    )
    print(f"Zombie alert sent for {service_type} {service_id}")


def send_success_alert(event):
    """Send success email when service stops cleanly"""
    service_id       = event.get('service_id')
    service_type     = event.get('service_type')
    region           = event.get('region')
    duration_seconds = event.get('duration_seconds', 0)

    # Convert seconds to minutes
    minutes = duration_seconds // 60
    seconds = duration_seconds % 60

    subject = f"✅ AWS Cost Guard — {service_type} Stopped Successfully"

    message = f"""
✅  SERVICE STOPPED SUCCESSFULLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service Type  : {service_type}
Service ID    : {service_id}
Region        : {region}
Time Taken    : {minutes} mins {seconds} secs

Your service has been stopped cleanly.
No further charges will be incurred for this service.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AWS Cost Guard — Automated Alert
    """

    sns.publish(
        TopicArn=arn:aws:sns:us-east-1:255260635688:aws-cost-guard-alerts,
        Subject=subject,
        Message=message
    )
    print(f"Success alert sent for {service_type} {service_id}")

