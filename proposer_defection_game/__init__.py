from otree.api import *
from otree.models import group

doc = """
A 6-player game: one proposer allocates €50 among all, others vote.
If majority accepts, proposer may defect and change the allocation.
This is repeated for 3 rounds.
"""

class C(BaseConstants):
    NAME_IN_URL = 'proposer_defection_game'
    PLAYERS_PER_GROUP = 6
    SUB_ROUNDS = 3  # Each proposer plays 3 sub-rounds
    NUM_ROUNDS = 12  # 6 × 3 = 18 rounds total
    TOTAL_AMOUNT = cu(50)


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    proposer_allocation = models.StringField()
    final_allocation = models.StringField()
    votes_accept = models.IntegerField(initial=0)
    votes_reject = models.IntegerField(initial=0)
    majority_accepts = models.BooleanField(initial=False)
    proposer_id = models.IntegerField()
    sub_round = models.IntegerField(initial=1)
    current_proposer_index = models.IntegerField(initial=1)
    last_proposer_index = models.IntegerField(initial=0)

    def get_allocation_dict(self):
        # Convert "10,5,10,10,5,10" → {1: 10, 2: 5, 3: 10, 4: 10, 5: 5, 6: 10}
        amounts = [int(x) for x in self.proposer_allocation.split(",")]
        return {i + 1: amount for i, amount in enumerate(amounts)}

    def majority_vote(self):
        # Count only votes that are not None
        self.votes_accept = sum([p.field_maybe_none('vote') or 0 for p in self.get_players() if not p.is_proposer])
        self.votes_reject = (C.PLAYERS_PER_GROUP - 1) - self.votes_accept
        self.majority_accepts = self.votes_accept > (C.PLAYERS_PER_GROUP - 1) / 2

    def advance_sub_round(self):
        # If current proposer hasn’t finished all sub-rounds
        if self.sub_round < C.SUB_ROUNDS:
            self.sub_round += 1
        else:
            # Move to next proposer
            self.sub_round = 1
            self.current_proposer_index += 1


class Player(BasePlayer):
    allocation_p1 = models.IntegerField(min=0, label="Player 1")
    allocation_p2 = models.IntegerField(min=0, label="Player 2")
    allocation_p3 = models.IntegerField(min=0, label="Player 3")
    allocation_p4 = models.IntegerField(min=0, label="Player 4")
    allocation_p5 = models.IntegerField(min=0, label="Player 5")
    allocation_p6 = models.IntegerField(min=0, label="Player 6")

    def get_allocations(self):
        return [
            self.allocation_p1,
            self.allocation_p2,
            self.allocation_p3,
            self.allocation_p4,
            self.allocation_p5,
            self.allocation_p6,
        ]
    is_proposer = models.BooleanField(initial=False)
    allocation = models.StringField(
        label="Enter the amount each participant receives (comma-separated, total must equal 50)",
    )
    vote = models.BooleanField(
        choices=[[True, 'Accept'], [False, 'Reject']],
        widget=widgets.RadioSelectHorizontal,
    )
    amount_received = models.CurrencyField(initial=0)
    total_earnings = models.CurrencyField(initial=0)

    @property
    def allocation_display(self):
        """Return a list of (player_id, amount) tuples for template display."""
        if not self.allocation:
            return []
        try:
            amounts = [int(x.strip()) for x in self.allocation.split(",")]
        except Exception:
            return []
        players = self.get_players()
        return [(p.id_in_group, amounts[p.id_in_group - 1]) for p in players]

    def proposed_amount(self):
        """Return how much this player was allocated in the current proposal."""
        if not self.group.proposer_allocation:
            return 0
        amounts = [int(x.strip()) for x in self.group.proposer_allocation.split(",")]
        return amounts[self.id_in_group - 1]

import random

def creating_session(subsession: Subsession):
    for group in subsession.get_groups():
        players = group.get_players()

        # Determine which proposer in this group for this round
        proposer_index = ((subsession.round_number - 1) // C.SUB_ROUNDS) % C.PLAYERS_PER_GROUP
        proposer = players[proposer_index]
        proposer.is_proposer = True
        group.proposer_id = proposer.id_in_group

        # Determine sub-round number (1, 2, or 3)
        group.sub_round = ((subsession.round_number - 1) % C.SUB_ROUNDS) + 1




'''
def set_payoffs(group: Group):
    players = group.get_players()
    if not group.majority_accepts:
        # all rejected
        for p in players:
            p.amount_received = cu(0)
    else:
        # apply final allocation (after defection if any)
        allocation_str = group.field_maybe_none('final_allocation') or group.proposer_allocation
        allocation_list = [int(x) for x in allocation_str.split(',')]
    for p, alloc in zip(players, allocation_list):
        p.amount_received = cu(alloc)
    # Update cumulative payoff tracking
    for p in players:
        if 'cumulative_earnings' not in p.participant.vars:
            p.participant.vars['cumulative_earnings'] = 0
        p.participant.vars['cumulative_earnings'] += int(p.amount_received)
        p.payoff = cu(p.participant.vars['cumulative_earnings'])'''


# PAGES
class Introduction(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

class ProposalWaitPage(WaitPage):
    # Only non-proposers should wait
    def is_displayed(self):
        return not self.is_proposer

    body_text = "Waiting for the proposer to make a decision..."


class ProposerDecision(Page):
    form_model = 'player'
    form_fields = [
        'allocation_p1',
        'allocation_p2',
        'allocation_p3',
        'allocation_p4',
        'allocation_p5',
        'allocation_p6',
    ]

    @staticmethod
    def is_displayed(player: Player):
        return player.is_proposer

    @staticmethod
    def vars_for_template(player: Player):
        # Count how many proposer decisions this player has made before
        previous_rounds = player.in_previous_rounds()
        proposer_rounds_completed = sum(1 for p in previous_rounds if p.is_proposer)

        sub_round = proposer_rounds_completed + 1  # Current proposer round number
        return {
            'sub_round': sub_round,
            'total_sub_rounds': C.SUB_ROUNDS,
            'total_amount': C.TOTAL_AMOUNT,
            'proposer_id': player.id_in_group,
        }

    @staticmethod
    def error_message(player: Player, values):
        total = sum(values.values())
        if total != C.TOTAL_AMOUNT:
            return f"The total must add up to €{C.TOTAL_AMOUNT}. Currently it adds up to €{total}."

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        allocations = player.get_allocations()
        group = player.group
        group.proposer_allocation = ','.join(str(a) for a in allocations)

class Voting(Page):
    form_model = 'player'
    form_fields = ['vote']

    @staticmethod
    def is_displayed(player: Player):
        return not player.is_proposer

    @staticmethod
    def vars_for_template(player: Player):
        group = player.group

        # Safely convert proposer_allocation "10,5,10,10,5,10" → {1:10, 2:5, ...}
        allocation_list = []
        if group.proposer_allocation:
            try:
                allocation_list = [int(x.strip()) for x in group.proposer_allocation.split(',')]
            except Exception:
                allocation_list = []
        allocation_dict = {i + 1: amt for i, amt in enumerate(allocation_list)}

        # ---- FIXED ROUND NUMBER CALCULATION ----
        # Count how many rounds this player has voted so far
        previous_rounds = player.in_previous_rounds()
        voting_rounds_completed = sum(1 for p in previous_rounds if not p.is_proposer)
        sub_round = group.sub_round  # your existing tracker for within-proposer rounds
        total_sub_rounds = C.SUB_ROUNDS  # e.g., 3
        round_display = f"Round {sub_round} of {total_sub_rounds}"

        if sub_round==1:
            proposer_changed=True
        else:
            proposer_changed=False

        # Identify current proposer
        current_proposer_id = None
        for p in group.get_players():
            if p.is_proposer:
                current_proposer_id = p.id_in_group


        return dict(
            allocation_dict=allocation_dict,
            sub_round=sub_round,
            total_sub_rounds=C.SUB_ROUNDS,
            current_proposer_id=current_proposer_id,
            proposer_changed=proposer_changed,
            round_display=round_display,
        )

    @staticmethod
    def app_after_this_page(player: Player, upcoming_apps):
        player.group.majority_vote()


class VotingWaitPage(WaitPage):
    wait_for_all_groups = False
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.majority_vote()  # call the group method
    def before_next_page(self, player: Player, timeout_happened):
        # Ensure fields are blank when page loads
        for field in [
            'allocation_p1', 'allocation_p2', 'allocation_p3', 'allocation_p4', 'allocation_p5', 'allocation_p6'
        ]:
            setattr(player, field, None)

class Defection(Page):
    form_model = 'player'
    form_fields = [
        'allocation_p1',
        'allocation_p2',
        'allocation_p3',
        'allocation_p4',
        'allocation_p5',
        'allocation_p6',
    ]

    @staticmethod
    def is_displayed(player: Player):
        group = player.group
        return player.is_proposer and group.majority_accepts

    @staticmethod
    def vars_for_template(player: Player):
        # Load proposer’s previous allocations (as string, e.g. "10,20,30,...")
        prev_alloc_str = player.group.proposer_allocation
        prev_alloc_list = []
        if prev_alloc_str:
            try:
                prev_alloc_list = [int(x.strip()) for x in prev_alloc_str.split(',')]
            except Exception:
                pass  # If something goes wrong, just leave empty

        return {
            'total_amount': C.TOTAL_AMOUNT,
            'proposer_id': player.id_in_group,
            'prev_allocations': prev_alloc_list,
        }

    @staticmethod
    def get_form_initial(player: Player):
        # Force all allocation fields to start empty
        return {f"allocation_p{i}": None for i in range(1, 7)}

    @staticmethod
    def error_message(player: Player, values):
        total = sum(values.values())
        if total != C.TOTAL_AMOUNT:
            return f"The total must add up to ${C.TOTAL_AMOUNT}. Currently it adds up to ${total}."

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        allocations = player.get_allocations()
        player.group.final_allocation = ','.join(str(a) for a in allocations)


class ResultsWaitPage(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        players = group.get_players()

        # Set payoffs for this sub-round
        if not group.majority_accepts:
            for p in players:
                p.amount_received = cu(0)
        else:
            allocation_str = group.field_maybe_none('final_allocation') or group.proposer_allocation
            allocation_list = [int(x) for x in allocation_str.split(',')]
            for p, alloc in zip(players, allocation_list):
                p.amount_received = cu(alloc)

        # Update cumulative payoffs for current proposer phase
        for p in players:
            if 'phase_earnings' not in p.participant.vars:
                p.participant.vars['phase_earnings'] = {}
            proposer_id = group.proposer_id
            # Initialize if first sub-round for this proposer
            if proposer_id not in p.participant.vars['phase_earnings']:
                p.participant.vars['phase_earnings'][proposer_id] = 0
            # Add current round's amount
            p.participant.vars['phase_earnings'][proposer_id] += int(p.amount_received)
            # Set current payoff (used for display in Results)
            p.payoff = cu(p.participant.vars['phase_earnings'][proposer_id])



class Results(Page):

    @staticmethod
    def vars_for_template(player: Player):

        # Split allocations into lists
        initial_alloc = [int(a) for a in player.group.proposer_allocation.split(',')]
        # Final allocation: 0s if majority rejected, else use defection/allocation
        if player.group.field_maybe_none('final_allocation') is None:
            final_alloc = [0] * len(initial_alloc)
        else:
            final_alloc = (
                [int(a) for a in player.group.field_maybe_none('final_allocation').split(',')]
                if player.group.field_maybe_none('final_allocation') else initial_alloc)
        allocation_pairs = list(zip(initial_alloc, final_alloc))
        has_defected = (final_alloc is not None and final_alloc != initial_alloc)
        phase_earnings = player.participant.vars.get('phase_earnings', {})
        proposer_id = player.group.proposer_id
        all_proposers = list(range(1, C.PLAYERS_PER_GROUP + 1))
        last_sub_round_for_proposer = player.group.sub_round == C.SUB_ROUNDS
        all_proposers_done = player.round_number == C.NUM_ROUNDS
        phase_total_for_current_proposer = phase_earnings.get(proposer_id, 0)

        if all_proposers_done:
            phase_earnings_display = {pid: phase_earnings.get(pid, 0) for pid in all_proposers}
        else:
            phase_earnings_display = {proposer_id: phase_earnings.get(proposer_id, 0)}

        return dict(
            allocation_pairs=allocation_pairs,
            phase_earnings=phase_earnings_display,
            last_sub_round_for_proposer=last_sub_round_for_proposer,
            phase_total_for_current_proposer=phase_total_for_current_proposer,
            all_proposers_done=all_proposers_done,
            proposer_id=proposer_id,
            sub_round=player.group.sub_round,
            sub_rounds=C.SUB_ROUNDS,
            has_defected=has_defected,
        )

class ThankYou(Page):
    @staticmethod
    def is_displayed(player: Player):
        # This page will show only at the very end of the experiment
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            message="Thank you for participating in this experiment!"
        )


page_sequence = [
    Introduction,
    ProposerDecision,
    ProposalWaitPage,
    Voting,
    VotingWaitPage,    # <-- ensure votes are counted
    Defection,
    ResultsWaitPage,
    Results,
    ThankYou,
]
