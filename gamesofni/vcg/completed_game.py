import random
from operator import attrgetter


class CompletedGame:
    def __init__(self, game=None, option=None, winner=None, amount=None, message=None):
        self.game = game
        self.option = option
        self.winner = winner
        self.amount = amount
        self.message = message

    def get_completed_info(self):
        return 'Game *' + self.game.name + '* just finished' + \
               ('\noption *' + self.option + '* has won' if self.option else '') + \
               ('\nwinner is *' + self.winner + '*' if self.winner else '') + \
               ('\namount to pay: *' + str(self.amount) + '*' if self.amount else '') + \
               ('\n' + self.message + '\n' if self.message else '') + \
               '\nGame info: ' + self.game.get_short_info()

    def to_json_encoded(self):
        json_completed_game = self.game.to_json_encoded()
        json_completed_game['id'] = self.game.team + self.game.name + str(self.game.start_date)
        if self.winner:
            json_completed_game['winner'] = self.winner
        if self.amount:
            json_completed_game['amount'] = self.amount

        return json_completed_game

    @staticmethod
    def get_completed_games(games):
        return [CompletedGame.finalize_game(game) for game in games]

    @staticmethod
    def finalize_game(game):
        if not game.bids:
            return CompletedGame(game=game, message='No bids were made in this game, game is closed without a winner.')

        if len(game.bids) == 1:
            return CompletedGame(game=game, winner=game.bids[0].user, amount=0, option=game.bids[0].option,
                                 message='There was only one bid made in this game. The winner doesn\'t pay.')
        if game.options:
            bid_options = {}
            for bid in game.bids:
                bid_options[bid.option] = bid_options.get(bid.option, 0) + bid.amount

            option_amounts = list(bid_options.values())
            winner_option = list(bid_options.keys())[option_amounts.index(max(option_amounts))]
            winner_amount = bid_options[winner_option]
            winner_bids = [bid for bid in game.bids if bid.option == winner_option]

            del bid_options[winner_option]
            option_amounts_without_winner = list(bid_options.values())
            second_option = list(bid_options.keys())[option_amounts_without_winner.index(max(option_amounts_without_winner))]
            second_amount = bid_options[second_option]

            if winner_amount == second_amount:
                return CompletedGame(game=game, option=winner_option, message='Nobody pays')

            winner_bids.sort(key=lambda b: b.amount, reverse=True)
            payers = {}
            for bid in winner_bids:
                effect = second_amount - (winner_amount - bid.amount)
                if effect > 0:
                    payers[bid.user] = effect
                else:
                    break

            if len(payers.keys()) == 0:
                return CompletedGame(game=game, option=winner_option, message='Nobody pays')

            message = ''
            for payer, amount in payers.items():
                message += 'user *' + payer + '* pays *' + str(amount) + '*\n'

            return CompletedGame(game=game, option=winner_option, message=message)
        else:
            winners_bid = max(game.bids, key=attrgetter('amount'))
            bids_without_winner = filter(lambda bid: bid.user != winners_bid.user, game.bids)
            second_bid = max(bids_without_winner, key=attrgetter('amount'))

            if winners_bid.amount == second_bid.amount:
                if bool(random.getrandbits(1)):
                    winner_name = winners_bid.user
                else:
                    winner_name = second_bid.user
                return CompletedGame(game=game, winner=winner_name, amount=second_bid.amount,
                                     message='Two persons bid same amount, tie was broken at random.')

            return CompletedGame(game=game, winner=winners_bid.user, amount=second_bid.amount)

    @staticmethod
    def get_completed_games_info(completed_games):
        if not completed_games:
            return ''
        return '\n\n'.join(completed_game.get_completed_info() for completed_game in completed_games) + '\n\n\n'
