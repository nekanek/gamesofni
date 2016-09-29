import json
import time
import re
import logging

import boto3
from boto3.dynamodb.conditions import Key

from vcg.game import Game
from vcg.utils import VcgException
from vcg.bid import Bid
from authorization import authorize
from scheduled import scheduled_invocation
import config

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    try:
        logger.info('Received event:\n' + json.dumps(event))
        event['request_id'] = context.aws_request_id
        resource = event.get('resource', None)

        if resource == '/oauth':
            return authorize(event, logger)

        source = event.get('source', None)
        if source == 'aws.events':
            if str(config.aws_account) != str(event.get('account')):
                return
            return scheduled_invocation(logger)

        if event.get('token', None) != str(config.slack_token):
            return

        if resource == '/info':
            return get_current_games(event)

        command = event.get('command', None)

        if command == '/bid':
            return user_bid_invocation(event)

        if command == '/create_game':
            return user_create_game(event)

        if command == '/set_timezone':
            return set_time_zone(event)

    except Exception as e:
        logger.exception(e.message)
        return {
            'response_type': 'ephemeral',
            'text': 'Sorry, something went wrong. '
                    'Please, send short description of what happened along with magic number to '
                    'sadnessexperts@gmail.com so we could fix it.'
                    '\nMagic number: ' + event.get('requestId', '')
        }


def set_time_zone(event):
    timezone = event.get('text', None)
    regex = '^utc([+-]\d\d?|0|$)$'  # accepts e.g. utc+3, utc-10, utc, utc0
    match = re.search(regex, timezone, re.I)

    if not match:
        return {
            'response_type': 'ephemeral',
            'text': 'It seems you input timezone is in the wrong format. '
                    '\nCorrect examples: utc+3 or utc-6 or utc+0' + command_info(event)
        }
    tz = match.group(1) if len(match.group(1)) > 0 else 0

    table_settings = boto3.resource('dynamodb').Table('settings')
    response = table_settings.update_item(
        Key={'team_id': event.get('team_id')},
        UpdateExpression='SET utc_offset = :offset, team_domain = :team_domain',
        ExpressionAttributeValues={
            ':offset': tz,
            ':team_domain': event.get('team_domain'),
        },
        ReturnValues='UPDATED_NEW'
    )

    logger.info('Set timezone success response from db: ' + str(response))
    return {
        'response_type': 'in_channel',
        'text': 'You successfully set timezone as utc ' + str(tz) +
                '\nYou can now create new games with /create_game command'
    }


def get_current_games(event):
    table_games = boto3.resource('dynamodb').Table('active_games')
    response = table_games.query(
        KeyConditionExpression=
        Key('team_id').eq(str(event.get('team_id')))
    )
    db_games = response['Items']
    logger.info('got success response from db: ' + str(db_games))

    if len(db_games) == 0:
        return {
            'response_type': 'ephemeral',
            'text': 'There are no active games at this moment'
        }

    message = Game.get_active_games_info(db_games)
    return {
        'response_type': 'ephemeral',
        'text': message
    }


def user_create_game(event):
    try:
        table_settings = boto3.resource('dynamodb').Table('settings')
        response = table_settings.query(
            KeyConditionExpression=
            Key('team_id').eq(str(event.get('team_id')))
        )
        db_settings = response['Items']
        logger.info('got success response from db: ' + str(db_settings))

        if len(db_settings) == 0:
            raise VcgException('It seems there was an error during authorisation process. '
                               '\nPlease, authorise this application again by clicking on '
                               'add to slack button on our website.')

        utc_offset_setting = db_settings[0].get('utc_offset', None)
        if not utc_offset_setting:
            raise VcgException('It seems you haven\'t set up timezone setting yet. '
                               'Please, do so with /set_timezone command.')

        game = Game.parse_from_command(event.get('text'), event.get('user_name'), event.get('team_id'), utc_offset_setting)
        db_games = get_active_game(event, game.name)

        if len(db_games) != 0:
            raise VcgException('game with this name is already active '
                               '\n' + Game.get_active_db_games_info(db_games))

        table_games = boto3.resource('dynamodb').Table('active_games')
        json_game = game.to_json_encoded()
        json_game['index'] = 1  # TODO: test whether this hack is faster than scan
        response = table_games.put_item(Item=json_game)
        logger.info('Save created gave success response from db: ' + str(response))
        response = '*' + event.get('user_name') + '* created new game! \n' + \
                   game.get_short_info() + \
                   '\n_(type /bid to participate)_'
        return {
            'response_type': 'in_channel',
            'text': response
        }

    except VcgException as e:
        return {
            'response_type': 'ephemeral',
            'text': 'Something went wrong with your attempt to create game: ' + str(e) + command_info(event)
        }


def user_bid_invocation(event):
    try:
        bid = Bid.parse_from_command(event.get('text'), event.get('user_name'))

        table_games = boto3.resource('dynamodb').Table('active_games')
        db_games = get_active_game(event, bid.game_name)
        if len(db_games) == 0:
            raise VcgException('There is no game with the name you specified')

        game = Game.parse_game(db_games[0])
        if game.end_date < int(time.time()):
            raise VcgException('This game has ended, you can\'t bid in it, sorry.')

        if bid.option:
            if not game.options or (bid.option not in game.options):
                raise VcgException('There is no such option in this game you tried to bid for, ' + game.get_options_info())

        else:
            if game.options:
                raise VcgException('We did not receive which option '
                                   'you would like to bid for in this game, ' + game.get_options_info())

        response = table_games.update_item(
            Key={
                'team_id': event.get('team_id'),
                'name': bid.game_name
            },
            UpdateExpression='SET bids.' + bid.user + '= :item',
            ExpressionAttributeValues={
                ':item': bid.to_json_encoded(),
            },
            ReturnValues='UPDATED_NEW'
        )

        return {
            'response_type': 'ephemeral',
            'text': 'Ok, ' + bid.get_bid_response_info()
        }

    except VcgException as e:
        return {
            'response_type': 'ephemeral',
            'text': 'Something went wrong with your bid: ' + str(e) + command_info(event)
        }


def get_active_game(event, game_name):
    table_games = boto3.resource('dynamodb').Table('active_games')
    response = table_games.query(
        KeyConditionExpression=
        Key('team_id').eq(str(event.get('team_id'))) &
        Key('name').eq(game_name)
    )
    db_games = response['Items']
    logger.info('Read active games successfully from db: ' + str(db_games))
    return db_games


def command_info(event):
    return '\nyour command was: ' + event.get('command') + ' ' + event.get('text')

