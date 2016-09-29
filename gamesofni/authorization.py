import json
import time
import requests
import boto3

import config


def authorize(event, logger):
    try:
        get_params = event.get('query', None)

        error = get_params.get('error', None)
        if error is not None and error == 'access_denied':
            logger.info('user denied authentication')
            return {'location': 'https://kurogitsune.github.io/gamesofni/cancel.html'}

        code = get_params.get('code', None)
        if code is None:
            raise OauthException('No oauth code was provided')

        logger.info('new team registration')

        oauth_url = 'https://slack.com/api/oauth.access'
        oauth_params = '?' \
                       + '&client_id=' + str(config.oauth['client_id']) \
                       + '&client_secret=' + str(config.oauth['client_secret']) \
                       + '&code=' + code
        response = requests.post(oauth_url + oauth_params)
        params = json.loads(response.text)
        logger.info('Got response from slack: ' + json.dumps(params))

        if not params.get('ok', False):
            raise OauthException('error when exchanging code for access_token')
        access_token = params.get('access_token', None)
        if access_token is not None:
            params['webhook_url'] = params.get('incoming_webhook').get('url')

            table_oauth = boto3.resource('dynamodb').Table('oauth')
            response = table_oauth.put_item(Item=params)
            logger.info('Put access token success response from db: ' + str(response))

            table_settings = boto3.resource('dynamodb').Table('settings')
            settings = {'team_id': params.get('team_id'),
                        'joined': int(time.time())}
            response = table_settings.put_item(Item=settings)
            logger.info('Saved settings success response from db: ' + str(response))

            return {'location': 'https://kurogitsune.github.io/gamesofni/landing.html'}

    except Exception as e:
        logger.exception(e)
        return {'location': 'https://kurogitsune.github.io/gamesofni/error.html'
                            '?requestId=' + str(event['request_id'])}


class OauthException(Exception):
    pass
