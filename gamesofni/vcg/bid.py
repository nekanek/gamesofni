from utils import VcgException


class Bid(object):
    def __init__(self, user=None, option=None, amount=None, game_name=None):
        self.user = user
        self.option = option
        self.amount = amount
        self.game_name = game_name

    def __str__(self):
        return 'User ' + self.user + ' bid ' + str(self.amount) + self.get_options_message()

    def get_bid_info(self):
        return 'User ' + self.user + ' bid ' + str(self.amount) + \
               self.get_options_message()

    def get_bid_response_info(self):
        return 'you ' + ' bid *' + str(self.amount) + '*' + \
               self.get_options_message() + \
               ' in game *' + self.game_name + '*'

    def get_options_message(self):
        return ' for option *' + self.option + '*' if self.option else ''

    def to_json_encoded(self):
        json_bid = {'user': self.user,
                    'amount': self.amount}
        if self.option:
            json_bid['option'] = self.option

        return str(json_bid)

    @staticmethod
    def parse_from_command(command, username):
        if not username:
            raise VcgException('empty username, how come 0_o')

        commands = command.split()
        # expected command format: game_name bid_amount [option]
        if len(commands) < 2 or len(commands) > 3:
            raise VcgException('not enough or too many words in command, something is wrong')

        with_option = len(commands) == 3
        try:
            bid_amount = int(commands[1])
        except ValueError:
            raise VcgException('your bid amount is not an integer')

        if bid_amount < 0:
            raise VcgException('you can\'t bid non-positive amounts')

        return Bid(user=username, option=(commands[2] if with_option else None), amount=bid_amount, game_name=commands[0])

    @staticmethod
    def parse_bids(bids):
        return [(Bid(user=bid['user'], option=bid.get('option', None), amount=bid['amount'])) for bid in bids]
