import json
import requests
import time

import boto3
from boto3.dynamodb.conditions import Key

from vcg.game import Game
from vcg.completed_game import CompletedGame


def scheduled_invocation(logger):
    db_games = get_completed_games()

    if len(db_games) == 0:
        logger.info('Got 0 finished games from db')
        return

    games = [Game.parse_game(db_game) for db_game in db_games]
    completed_games = CompletedGame.get_completed_games(games)

    completed_game_items = [game.to_json_encoded() for game in completed_games]
    logger.info('Got completed games from db: ' + str(completed_games))

    insert_request_items = wrap_dynamo_batch_insert(completed_game_items, 'completed_games')
    dynamodb = boto3.resource('dynamodb')

    response = dynamodb.batch_write_item(RequestItems=insert_request_items)
    logger.info('Archiving completed games success response from db: ' + str(response))

    completed_games_by_team = {}
    for game in completed_games:
        team_games = completed_games_by_team.get(game.game.team, [])
        team_games.append(game)
        completed_games_by_team[game.game.team] = team_games

    team_names = completed_games_by_team.keys()

    team2url = get_access_codes(team_names, dynamodb, logger)

    for team in team_names:
        games_info = CompletedGame.get_completed_games_info(completed_games_by_team[team])
        requests.post(team2url[team], data=json.dumps({'text': games_info}))

    delete_request_items = wrap_dynamo_batch_delete(completed_games_by_team, 'active_games')
    response = dynamodb.batch_write_item(RequestItems=delete_request_items)
    logger.info('Deleted completed games from active_games table successfully: ' + str(response))


def get_access_codes(team_names, dynamodb, logger):
    response = dynamodb.meta.client.batch_get_item(RequestItems={
        'oauth': {
            'Keys': [{'team_id': team} for team in team_names],
            'ProjectionExpression': 'team_id, webhook_url'
        }
    })
    team2url = response['Responses']['oauth']
    team2url = {team_info['team_id']: team_info['webhook_url'] for team_info in team2url}
    logger.info('Got response from db team-url oauth: ' + str(team2url))
    logger.info('UnprocessedKeys for team-url oauth: ' + str(response['UnprocessedKeys']))
    return team2url


def get_completed_games():
    table_games = boto3.resource('dynamodb').Table('active_games')
    now = int(time.time())
    response = table_games.query(
        IndexName='end_date-index',
        KeyConditionExpression=Key('index').eq(1) & Key('end_date').lt(now)
    )
    db_games = response['Items']
    return db_games


def wrap_dynamo_batch_insert(items, table_name):
    items_array = []
    for item in items:
        items_array.append({'PutRequest': {'Item': item}})
    return {table_name: items_array}


def wrap_dynamo_batch_delete(completed_games_by_team, table_name):
    items_array = []
    for team, completed_games in completed_games_by_team.items():
        for completed_game in completed_games:
            items_array.append({'DeleteRequest': {'Key': {'team_id': team, 'name': completed_game.game.name}}})
    return {table_name: items_array}
