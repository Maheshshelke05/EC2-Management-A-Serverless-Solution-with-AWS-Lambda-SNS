import json
import boto3
import time

# AWS Clients
ec2 = boto3.client('ec2')
sns = boto3.client('sns')

# Configuration
INSTANCE_ID = "i-0e068c43430210bff"
SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:your account id:ec2-state-notify"

def publish_sms(message):
    """Send SMS notification"""
    try:
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        print(f"SMS sent: {response['MessageId']}")
        return True
    except Exception as e:
        print(f"SMS error: {str(e)}")
        return False

def lambda_handler(event, context):
    """Main Lambda handler"""
    
    # Extract action from event
    action = ""
    if isinstance(event, dict):
        action = event.get('action') or (event.get('queryStringParameters') or {}).get('action','')
        if not action and event.get('body'):
            try:
                action = json.loads(event['body']).get('action','')
            except:
                pass

    action = (action or "").lower()
    print(f"Action received: {action}")

    try:
        if action == 'test':
            success = publish_sms(f"TEST: EC2 Monitor - Instance {INSTANCE_ID}")
            return {'result': 'test', 'sms_sent': success}

        if action == 'start':
            status_resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
            current_state = status_resp['Reservations'][0]['Instances'][0]['State']['Name']
            if current_state == 'running':
                publish_sms(f"🟢 EC2 - ALREADY RUNNING")
                return {'result': 'already_running'}
            
            publish_sms(f"🟡 EC2 - STARTING...")
            ec2.start_instances(InstanceIds=[INSTANCE_ID])
            waiter = ec2.get_waiter('instance_running')
            waiter.wait(InstanceIds=[INSTANCE_ID], WaiterConfig={'Delay': 10, 'MaxAttempts': 12})
            publish_sms(f"✅ EC2 - STARTED SUCCESS")
            return {'result': 'started'}

        if action == 'stop':
            publish_sms(f"🟡 EC2 - STOPPING...")
            ec2.stop_instances(InstanceIds=[INSTANCE_ID])
            waiter = ec2.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=[INSTANCE_ID], WaiterConfig={'Delay': 10, 'MaxAttempts': 12})
            publish_sms(f"🛑 EC2 - STOPPED SUCCESS")
            return {'result': 'stopped'}

        resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
        state = resp['Reservations'][0]['Instances'][0]['State']['Name']
        state_icon = '🟢' if state == 'running' else '🛑'
        publish_sms(f"{state_icon} EC2 - {state.upper()}")
        return {'result': 'status', 'state': state}
        
    except Exception as e:
        error_msg = f"❌ EC2 ERROR: {str(e)}"
        publish_sms(error_msg)
        return {'result': 'error', 'error': error_msg}