import json
import boto3
from decimal import Decimal
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')

def get_boat(entries, phone):
    r=[i for i in entries if 'whatsapp' in i['data']['boat'] and phone in i['data']['boat']['whatsapp']]
    if len(r) == 0:
        return
    item = r[0]
    return item['data']['boat']
    
def update_database(boat, timestamp, **kwargs):
    table = dynamodb.Table('public_location')
    p=table.scan()
    id = f"{boat['oga_no']}"
    r=[i for i in p['Items'] if id == i['id']]
    if len(r) > 0:
        item = r[0]
    else:
        item = { 'id': id, 'type': 'boat', **boat }
    if 'location' in kwargs:
        location = kwargs['location']
        item['location'] = {**location, 'timestamp': timestamp}
    if 'visible' in kwargs:
        visible = kwargs['visible']
        item['visible'] = visible
    table.put_item(Item=item)

def set_location(timestamp, message):
    # print('location', message)
    boat = get_boat(message['from'])
    if boat is not None:
        update_database(boat, timestamp,  location=message['location'])

def set_new_number(entries, phone, body):
    r=[i for i in entries if i['data']['boat']['name'].lower() in body]
    if len(r) == 0:
        print('unknown number', phone)
        return None
    if len(r) > 1:
        print('message matches more than one boat', r)
        return None
    item = r[0]
    item['data']['boat']['whatsapp'] = [phone]
    print(item)
    table = dynamodb.Table('member_entries')
    table.put_item(Item=item)
    return item['data']['boat']

def show_hide(body, timestamp, boat):
    if 'show' in body:
        print('show', timestamp, boat)
        update_database(boat, timestamp,  visible=True)
    elif 'hide' in body:
        print('hide', timestamp, boat)
        update_database(boat, timestamp,  visible=False)
    
def handle_text(timestamp, message):
    body = message['text']['body'].lower()
    phone = message['from']
    # print('text', timestamp, phone, body)
    entriesTable = dynamodb.Table('member_entries')
    entries=entriesTable.scan()['Items']
    boat = get_boat(entries, phone)
    print('boat', boat)
    if boat is None:
        boat = set_new_number(entries, phone, body)
        if boat is None:
            return
    show_hide(body, timestamp, boat)

def handle_message(message):
    timestamp = datetime.fromtimestamp(int(message['timestamp']), timezone.utc).isoformat().replace('+00:00','Z')
    # print('handle_message of type', message['type'])
    if 'location' in message:
        set_location(timestamp, message)
    elif 'text' in message:
        handle_text(timestamp, message)
    else:
        print('unknown', timestamp, message)

def handle_change(change):
    # print(change['field'])
    val = change['value']
    # print(val['messaging_product']) 
    # print(val['metadata'])
    # print(val['contacts'])
    for message in val['messages']:
        handle_message(message)

def lambda_handler(event, context):
    # print(json.dumps(event))
    http = event['requestContext']['http']
    if http['method'] == 'GET':
        try:
            if event['queryStringParameters']['hub.mode'] == 'subscribe':
                if '677a76cb-29d0-49c9-8700-7a3e05fe8b2e' == event['queryStringParameters']['hub.verify_token']:
                    return {
                        'statusCode': 200,
                        'body': json.dumps(int(event['queryStringParameters']['hub.challenge']))
                    }
        except:
            pass
        return {
            'statusCode': 400,
            'body': json.dumps('bad request')
        }
    elif http['method'] == 'POST':
        body = json.loads(event['body'], parse_float=Decimal)
        for item in body['entry']:
            for change in item['changes']:
                handle_change(change)
        pass
    else:
        # TODO implement
        pass
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
