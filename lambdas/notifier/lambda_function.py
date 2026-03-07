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

        elif alert_type == 'IDLE':
            send_idle_alert(event)

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
        TopicArn='arn:aws:sns:us-east-1:255260635688:aws-cost-guard-alerts',
        Subject=subject,
        Message=message
    )
    print(f"Success alert sent for {service_type} {service_id}")


def send_idle_alert(event):
    """Send alert email when service running too long"""
    service_id    = event.get('service_id')
    service_type  = event.get('service_type')
    instance_type = event.get('instance_type')
    hours_running = event.get('hours_running')

    subject = f"⏰ AWS Cost Guard — {service_type} Running for {hours_running} Hours!"

    message = f"""
⏰  IDLE SERVICE ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service Type  : {service_type}
Service ID    : {service_id}
Instance Type : {instance_type}
Running For   : {hours_running} hours

This service has been running for over {hours_running} hours.
It may be idle and consuming your AWS credits!

IF YOU ARE DONE WORKING:
→ Login to AWS Console
→ Stop this instance now!
→ Save your credits 💰

IF YOU ARE STILL WORKING:
→ Ignore this email ✅
→ You will be notified again 
  after another {hours_running} hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━
AWS Cost Guard — Idle Alert
    """

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=subject,
        Message=message
    )
    print(f"Idle alert sent for {service_type} {service_id}")


