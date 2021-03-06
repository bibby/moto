from __future__ import unicode_literals

import boto
import boto3
from boto3.dynamodb.conditions import Key
import sure  # noqa
from freezegun import freeze_time
from boto.exception import JSONResponseError
from moto import mock_dynamodb2
from tests.helpers import requires_boto_gte
try:
    from boto.dynamodb2.fields import HashKey
    from boto.dynamodb2.table import Table
    from boto.dynamodb2.table import Item
    from boto.dynamodb2.exceptions import ConditionalCheckFailedException, ItemNotFound
except ImportError:
    pass


def create_table():
    table = Table.create('messages', schema=[
        HashKey('forum_name')
    ], throughput={
        'read': 10,
        'write': 10,
    })
    return table


@requires_boto_gte("2.9")
@mock_dynamodb2
@freeze_time("2012-01-14")
def test_create_table():
    create_table()
    expected = {
        'Table': {
            'AttributeDefinitions': [
                {'AttributeName': 'forum_name', 'AttributeType': 'S'}
            ],
            'ProvisionedThroughput': {
                'NumberOfDecreasesToday': 0, 'WriteCapacityUnits': 10, 'ReadCapacityUnits': 10
            },
            'TableSizeBytes': 0,
            'TableName': 'messages',
            'TableStatus': 'ACTIVE',
            'KeySchema': [
                {'KeyType': 'HASH', 'AttributeName': 'forum_name'}
            ],
            'ItemCount': 0, 'CreationDateTime': 1326499200.0,
            'GlobalSecondaryIndexes': [],
        }
    }
    conn = boto.dynamodb2.connect_to_region(
        'us-west-2',
        aws_access_key_id="ak",
        aws_secret_access_key="sk"
    )

    conn.describe_table('messages').should.equal(expected)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_delete_table():
    create_table()
    conn = boto.dynamodb2.layer1.DynamoDBConnection()
    conn.list_tables()["TableNames"].should.have.length_of(1)

    conn.delete_table('messages')
    conn.list_tables()["TableNames"].should.have.length_of(0)

    conn.delete_table.when.called_with('messages').should.throw(JSONResponseError)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_update_table_throughput():
    table = create_table()
    table.throughput["read"].should.equal(10)
    table.throughput["write"].should.equal(10)

    table.update(throughput={
        'read': 5,
        'write': 6,
    })

    table.throughput["read"].should.equal(5)
    table.throughput["write"].should.equal(6)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_item_add_and_describe_and_update():
    table = create_table()

    data = {
        'forum_name': 'LOLCat Forum',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
    }

    table.put_item(data=data)
    returned_item = table.get_item(forum_name="LOLCat Forum")
    returned_item.should_not.be.none

    dict(returned_item).should.equal({
        'forum_name': 'LOLCat Forum',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
    })

    returned_item['SentBy'] = 'User B'
    returned_item.save(overwrite=True)

    returned_item = table.get_item(
        forum_name='LOLCat Forum'
    )
    dict(returned_item).should.equal({
        'forum_name': 'LOLCat Forum',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User B',
    })


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_item_partial_save():
    table = create_table()

    data = {
        'forum_name': 'LOLCat Forum',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
    }

    table.put_item(data=data)
    returned_item = table.get_item(forum_name="LOLCat Forum")

    returned_item['SentBy'] = 'User B'
    returned_item.partial_save()

    returned_item = table.get_item(
        forum_name='LOLCat Forum'
    )
    dict(returned_item).should.equal({
        'forum_name': 'LOLCat Forum',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User B',
    })


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_item_put_without_table():
    conn = boto.dynamodb2.layer1.DynamoDBConnection()

    conn.put_item.when.called_with(
        table_name='undeclared-table',
        item={
            'forum_name': 'LOLCat Forum',
            'Body': 'http://url_to_lolcat.gif',
            'SentBy': 'User A',
        }
    ).should.throw(JSONResponseError)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_get_item_with_undeclared_table():
    conn = boto.dynamodb2.layer1.DynamoDBConnection()

    conn.get_item.when.called_with(
        table_name='undeclared-table',
        key={"forum_name": {"S": "LOLCat Forum"}},
    ).should.throw(JSONResponseError)


@requires_boto_gte("2.30.0")
@mock_dynamodb2
def test_delete_item():
    table = create_table()

    item_data = {
        'forum_name': 'LOLCat Forum',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
        'ReceivedTime': '12/9/2011 11:36:03 PM',
    }
    item = Item(table, item_data)
    item.save()
    table.count().should.equal(1)

    response = item.delete()

    response.should.equal(True)

    table.count().should.equal(0)

    item.delete().should.equal(False)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_delete_item_with_undeclared_table():
    conn = boto.dynamodb2.layer1.DynamoDBConnection()

    conn.delete_item.when.called_with(
        table_name='undeclared-table',
        key={"forum_name": {"S": "LOLCat Forum"}},
    ).should.throw(JSONResponseError)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_query():
    table = create_table()

    item_data = {
        'forum_name': 'the-key',
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
        'ReceivedTime': '12/9/2011 11:36:03 PM',
    }
    item = Item(table, item_data)
    item.save(overwrite=True)
    table.count().should.equal(1)
    table = Table("messages")

    results = table.query(forum_name__eq='the-key')
    sum(1 for _ in results).should.equal(1)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_query_with_undeclared_table():
    conn = boto.dynamodb2.layer1.DynamoDBConnection()

    conn.query.when.called_with(
        table_name='undeclared-table',
        key_conditions={"forum_name": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": "the-key"}]}}
    ).should.throw(JSONResponseError)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_scan():
    table = create_table()

    item_data = {
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
        'ReceivedTime': '12/9/2011 11:36:03 PM',
    }
    item_data['forum_name'] = 'the-key'

    item = Item(table, item_data)
    item.save()

    item['forum_name'] = 'the-key2'
    item.save(overwrite=True)

    item_data = {
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User B',
        'ReceivedTime': '12/9/2011 11:36:03 PM',
        'Ids': set([1, 2, 3]),
        'PK': 7,
    }
    item_data['forum_name'] = 'the-key3'
    item = Item(table, item_data)
    item.save()

    results = table.scan()
    sum(1 for _ in results).should.equal(3)

    results = table.scan(SentBy__eq='User B')
    sum(1 for _ in results).should.equal(1)

    results = table.scan(Body__beginswith='http')
    sum(1 for _ in results).should.equal(3)

    results = table.scan(Ids__null=False)
    sum(1 for _ in results).should.equal(1)

    results = table.scan(Ids__null=True)
    sum(1 for _ in results).should.equal(2)

    results = table.scan(PK__between=[8, 9])
    sum(1 for _ in results).should.equal(0)

    results = table.scan(PK__between=[5, 8])
    sum(1 for _ in results).should.equal(1)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_scan_with_undeclared_table():
    conn = boto.dynamodb2.layer1.DynamoDBConnection()

    conn.scan.when.called_with(
        table_name='undeclared-table',
        scan_filter={
            "SentBy": {
                "AttributeValueList": [{
                    "S": "User B"}
                ],
                "ComparisonOperator": "EQ"
            }
        },
    ).should.throw(JSONResponseError)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_write_batch():
    table = create_table()

    with table.batch_write() as batch:
        batch.put_item(data={
            'forum_name': 'the-key',
            'subject': '123',
            'Body': 'http://url_to_lolcat.gif',
            'SentBy': 'User A',
            'ReceivedTime': '12/9/2011 11:36:03 PM',
        })
        batch.put_item(data={
            'forum_name': 'the-key2',
            'subject': '789',
            'Body': 'http://url_to_lolcat.gif',
            'SentBy': 'User B',
            'ReceivedTime': '12/9/2011 11:36:03 PM',
        })

    table.count().should.equal(2)
    with table.batch_write() as batch:
        batch.delete_item(
            forum_name='the-key',
            subject='789'
        )

    table.count().should.equal(1)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_batch_read():
    table = create_table()

    item_data = {
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User A',
        'ReceivedTime': '12/9/2011 11:36:03 PM',
    }
    item_data['forum_name'] = 'the-key1'
    item = Item(table, item_data)
    item.save()

    item = Item(table, item_data)
    item_data['forum_name'] = 'the-key2'
    item.save(overwrite=True)

    item_data = {
        'Body': 'http://url_to_lolcat.gif',
        'SentBy': 'User B',
        'ReceivedTime': '12/9/2011 11:36:03 PM',
        'Ids': set([1, 2, 3]),
        'PK': 7,
    }
    item = Item(table, item_data)
    item_data['forum_name'] = 'another-key'
    item.save(overwrite=True)

    results = table.batch_get(
        keys=[
            {'forum_name': 'the-key1'},
            {'forum_name': 'another-key'},
        ]
    )

    # Iterate through so that batch_item gets called
    count = len([x for x in results])
    count.should.equal(2)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_get_key_fields():
    table = create_table()
    kf = table.get_key_fields()
    kf[0].should.equal('forum_name')


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_get_missing_item():
    table = create_table()
    table.get_item.when.called_with(forum_name='missing').should.throw(ItemNotFound)


@requires_boto_gte("2.9")
@mock_dynamodb2
def test_get_special_item():
    table = Table.create('messages', schema=[
        HashKey('date-joined')
    ], throughput={
        'read': 10,
        'write': 10,
    })

    data = {
        'date-joined': 127549192,
        'SentBy': 'User A',
    }
    table.put_item(data=data)
    returned_item = table.get_item(**{'date-joined': 127549192})
    dict(returned_item).should.equal(data)


@mock_dynamodb2
def test_update_item_remove():
    conn = boto.dynamodb2.connect_to_region("us-west-2")
    table = Table.create('messages', schema=[
        HashKey('username')
    ])

    data = {
        'username': "steve",
        'SentBy': 'User A',
        'SentTo': 'User B',
    }
    table.put_item(data=data)
    key_map = {
        "S": "steve"
    }

    # Then remove the SentBy field
    conn.update_item("messages", key_map, update_expression="REMOVE :SentBy, :SentTo")

    returned_item = table.get_item(username="steve")
    dict(returned_item).should.equal({
        'username': "steve",
    })


@mock_dynamodb2
def test_update_item_set():
    conn = boto.dynamodb2.connect_to_region("us-west-2")
    table = Table.create('messages', schema=[
        HashKey('username')
    ])

    data = {
        'username': "steve",
        'SentBy': 'User A',
    }
    table.put_item(data=data)
    key_map = {
        "S": "steve"
    }

    conn.update_item("messages", key_map, update_expression="SET foo=:bar, blah=:baz REMOVE :SentBy")

    returned_item = table.get_item(username="steve")
    dict(returned_item).should.equal({
        'username': "steve",
        'foo': 'bar',
        'blah': 'baz',
    })


@mock_dynamodb2
def test_failed_overwrite():
    table = Table.create('messages', schema=[
        HashKey('id'),
    ], throughput={
        'read': 7,
        'write': 3,
    })

    data1 = {'id': '123', 'data': '678'}
    table.put_item(data=data1)

    data2 = {'id': '123', 'data': '345'}
    table.put_item(data=data2, overwrite=True)

    data3 = {'id': '123', 'data': '812'}
    table.put_item.when.called_with(data=data3).should.throw(ConditionalCheckFailedException)

    returned_item = table.lookup('123')
    dict(returned_item).should.equal(data2)

    data4 = {'id': '124', 'data': 812}
    table.put_item(data=data4)

    returned_item = table.lookup('124')
    dict(returned_item).should.equal(data4)


@mock_dynamodb2
def test_conflicting_writes():
    table = Table.create('messages', schema=[
        HashKey('id'),
    ])

    item_data = {'id': '123', 'data': '678'}
    item1 = Item(table, item_data)
    item2 = Item(table, item_data)
    item1.save()

    item1['data'] = '579'
    item2['data'] = '912'

    item1.save()
    item2.save.when.called_with().should.throw(ConditionalCheckFailedException)


"""
boto3
"""


@mock_dynamodb2
def test_boto3_conditions():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName='users',
        KeySchema=[
            {
                'AttributeName': 'username',
                'KeyType': 'HASH'
            },
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'username',
                'AttributeType': 'S'
            },
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    table = dynamodb.Table('users')

    table.put_item(Item={'username': 'johndoe'})
    table.put_item(Item={'username': 'janedoe'})

    response = table.query(
        KeyConditionExpression=Key('username').eq('johndoe')
    )
    response['Count'].should.equal(1)
    response['Items'].should.have.length_of(1)
    response['Items'][0].should.equal({"username": "johndoe"})
