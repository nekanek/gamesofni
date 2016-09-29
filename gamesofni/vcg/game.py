import json
import time
import ast

import utils
from utils import VcgException
from .bid import Bid


class Game(object):
    def __init__(self, team, name, creator, start_date,
                 end_date, options, bids, utc_offset):
        self.team = team
        self.name = name
        self.creator = creator
        self.start_date = start_date
        self.end_date = end_date
        self.options = options
        self.bids = Bid.parse_bids(bids) if bids else []
        self.utc_offset = utc_offset

    def get_short_info(self):
        message = 'Name of the game: ' + '*' + self.name + '*' \
                  + '\nstarted on ' + utils.get_formatted_time(utils.get_local_time(self.start_date, self.utc_offset)) \
                  + '\nends on ' + utils.get_formatted_time(utils.get_local_time(self.end_date, self.utc_offset))

        message += '\n' + self.get_options_info()

        if utils.DEBUGGING:
            message += '\nextra little secret debugging info: '
            if self.bids:
                message += 'current bids are: ' + ', '.join(map(lambda bid: bid.get_bid_info(), self.bids))
            else:
                message += 'there are no bids yet'
            message += ', game creator: ' + self.creator

        return message

    def get_options_info(self):
        if self.options:
            return 'options to vote for: ' + '*' + ', '.join(self.options) + '*'
        else:
            return 'voting for this game is *without options*'

    def to_json_encoded(self):
        bids = {bid.user: bid.to_json_encoded() for bid in self.bids} if self.bids else {}
        json_game = {'team_id': self.team,
                     'name': self.name,
                     'creator': self.creator,
                     'start_date': self.start_date,
                     'end_date': self.end_date,
                     'bids': bids,
                     'utc_offset': self.utc_offset
                     }
        if self.options:
            json_game['options'] = json.dumps(self.options)
        return json_game

    @staticmethod
    def get_active_db_games_info(db_games):
        now = int(time.time())
        return '\n\n'.join([Game.parse_game(db_game).get_short_info() for db_game in db_games
                            if Game.parse_game(db_game).end_date > now]) + '\n\n'

    @staticmethod
    def get_active_games_info(db_games):
        if not db_games:
            return 'There are no games in progress.'
        games_info = ''
        now = int(time.time())
        for db_game in db_games:
            game = Game.parse_game(db_game)
            if game.end_date > now:
                games_info += game.get_short_info() + '\n\n'
        return 'Games in progress are:\n' + games_info

    @staticmethod
    def parse_game(db_game):
        bids = list(db_game['bids'].values())
        options = db_game.get('options', None)
        if options:
            options = ast.literal_eval(options)
        return Game(
            team=db_game['team_id'],
            name=db_game['name'],
            creator=db_game['creator'],
            start_date=db_game['start_date'],
            end_date=db_game['end_date'],
            options=options,
            bids=map(ast.literal_eval, bids) if bids else [],
            utc_offset=db_game['utc_offset']
        )

    @staticmethod
    def parse_from_command(command, username, team, utc_offset):
        if not username:
            raise VcgException('empty username, how come 0_o')

        # expected command format: game_name end_time(DD-MM-YY HH:MM) [option1 option2....]
        commands = command.split()
        if len(commands) < 3 or len(commands) > 50:
            raise VcgException('not enough or too many words in command, something is wrong')

        try:
            local_end_date = int(utils.get_unix_time_from_date(commands[1] + ' ' + commands[2]))
        except ValueError:
            raise VcgException('end time of your game seems to be in wrong format')

        game_end_time_utc = utils.get_utc_time(local_end_date, utc_offset)

        start_date = int(time.time())
        if start_date > game_end_time_utc:
            raise VcgException('end time of your game seems to be in the past')

        with_options = len(commands) > 3
        return Game(
            team=team,
            name=commands[0],
            creator=username,
            start_date=start_date,
            end_date=game_end_time_utc,
            options=commands[3:] if with_options else None,
            bids=[],
            utc_offset=utc_offset
        )
