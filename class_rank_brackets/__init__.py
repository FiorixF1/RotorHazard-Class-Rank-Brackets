''' Class ranking method: Brackets '''

import logging
import RHUtils
from eventmanager import Evt
from RHRace import StartBehavior
from Results import RaceClassRankMethod
from RHUI import UIField, UIFieldType, UIFieldSelectOption

logger = logging.getLogger(__name__)

# MultiGP doc link: https://docs.google.com/document/d/1e2poO4otvcKop1ZcQ1tQZ36ztmrWm1cMIg1VS9mHLeU/edit#heading=h.c7d32jvxr7wf

def apply_tiebreaker(leaderboard, qualifier, first_position, second_position):
    # assume that first_position < second_position, we decrease them by one to get a 0-based index
    first_position -= 1
    second_position -= 1

    # extract the two pilots from the leaderboard
    first_leaderboard_object = leaderboard[first_position]
    second_leaderboard_object = leaderboard[second_position]

    # if the two pilots exist...
    if first_leaderboard_object != None and second_leaderboard_object != None:
        # ...get their pilot id...
        first_pilot_id = first_leaderboard_object['pilot_id']
        second_pilot_id = second_leaderboard_object['pilot_id']

        # ...and use it to get their position in the qualifier class
        first_qualifier_object = list(filter(lambda x: x['pilot_id'] == first_pilot_id, qualifier))[0]
        second_qualifier_object = list(filter(lambda x: x['pilot_id'] == second_pilot_id, qualifier))[0]

        # if the second pilot has a better position than the first pilot in the qualifier class...
        if second_qualifier_object['position'] < first_qualifier_object['position']:
            # ...promote it by swapping the two positions in the leaderboard
            first_leaderboard_object['position'], second_leaderboard_object['position'] = second_leaderboard_object['position'], first_leaderboard_object['position']
            # (do not forget to swap the two pilots also in the array, updating 'position' is not enough :P )
            leaderboard[first_position], leaderboard[second_position] = leaderboard[second_position], leaderboard[first_position]



def build_leaderboard_object_basic(rhapi, position, slot, result):
    return {
        'pilot_id': slot['pilot_id'],
        'callsign': slot['callsign'],
        'team_name': slot['team_name'],
        'position': position,
        'result': result
    }



def build_leaderboard_object(rhapi, position, heats, heat_number, heat_position, result):
    if heat_number <= len(heats):
        heat = heats[heat_number-1]
        # for robustness, don't use heat_results but get results from Round 1 instead
        races = rhapi.db.races_by_heat(heat.id)
        if races:
            race_result = rhapi.db.race_results(races[0])
            if race_result:
                heat_leaderboard = race_result[race_result['meta']['primary_leaderboard']]
                slot = heat_leaderboard[heat_position-1]

                return {
                    'pilot_id': slot['pilot_id'],
                    'callsign': slot['callsign'],
                    'team_name': slot['team_name'],
                    'position': position,
                    'result': result
                }

    return None



####################################################################################################

def brackets(rhapi, race_class, args):
    """ look for qualifier results """
    if int(args["qualifier_class"]) == int(race_class.id):
        rhapi.ui.message_alert(rhapi.__("Failed building ranking, brackets cannot use themselves as qualifier class"))
        return {}, {}

    qualifier_result = None
    for raceclass in rhapi.db.raceclasses:
        if int(raceclass.id) == int(args["qualifier_class"]):
            qualifier_result = rhapi.db.raceclass_results(raceclass)

    if not qualifier_result:
        rhapi.ui.message_alert(rhapi.__("Failed building ranking, qualifier result not available"))
        return {}, {}

    qualifier = qualifier_result[qualifier_result['meta']['primary_leaderboard']]

    """ build leaderboard """
    heats = rhapi.db.heats_by_class(race_class.id)

    leaderboard = [
        None,  # top 4 positions are handled later due to CTA logic
        None,
        None,
        None,
        build_leaderboard_object(rhapi, 5,  heats, 13, 3, "3° in Heat 13"),
        build_leaderboard_object(rhapi, 6,  heats, 13, 4, "4° in Heat 13"),
        build_leaderboard_object(rhapi, 7,  heats, 12, 3, "3° in Heat 12"),
        build_leaderboard_object(rhapi, 8,  heats, 12, 4, "4° in Heat 12"),
        build_leaderboard_object(rhapi, 9,  heats, 9,  3, "3° in Heat 9"),   # to be fixed Q1
        build_leaderboard_object(rhapi, 10, heats, 10, 3, "3° in Heat 10"),  # to be fixed Q1
        build_leaderboard_object(rhapi, 11, heats, 9,  4, "4° in Heat 9"),   # to be fixed Q2
        build_leaderboard_object(rhapi, 12, heats, 10, 4, "4° in Heat 10"),  # to be fixed Q2
        build_leaderboard_object(rhapi, 13, heats, 5,  3, "3° in Heat 5"),   # to be fixed Q3
        build_leaderboard_object(rhapi, 14, heats, 7,  3, "3° in Heat 7"),   # to be fixed Q3
        build_leaderboard_object(rhapi, 15, heats, 5,  4, "4° in Heat 5"),   # to be fixed Q4
        build_leaderboard_object(rhapi, 16, heats, 7,  4, "4° in Heat 7")    # to be fixed Q4
    ]

    """ apply qualifier results to resolve ties """
    apply_tiebreaker(leaderboard, qualifier, 9, 10)
    apply_tiebreaker(leaderboard, qualifier, 11, 12)
    apply_tiebreaker(leaderboard, qualifier, 13, 14)
    apply_tiebreaker(leaderboard, qualifier, 15, 16)

    """ apply Chase the Ace and Iron Man rule """
    if 'chase_the_ace' in args and args['chase_the_ace']:
        # verify if Iron Man rule can be applied
        if 'iron_man' in args and args['iron_man']:
            IS_IRON_MAN_AVAILABLE = True
            tq_object = list(filter(lambda x: x['position'] == 1, qualifier))[0]
            tq_pilot_id = tq_object['pilot_id']

            # verify that the pilot holding the TQ has won all heats before the final
            for heat in heats[:-1]:
                # for robustness, don't use heat_results but get results from Round 1 instead
                races = rhapi.db.races_by_heat(heat.id)
                if races:
                    race_result = rhapi.db.race_results(races[0])
                    if race_result:
                        heat_leaderboard = race_result[race_result['meta']['primary_leaderboard']]
                        pilot_ids = list(map(lambda x: x['pilot_id'], heat_leaderboard))
                        winner_pilot_id = heat_leaderboard[0]['pilot_id']
                        if tq_pilot_id in pilot_ids and winner_pilot_id != tq_pilot_id:
                            IS_IRON_MAN_AVAILABLE = False
                            break
        else:
            IS_IRON_MAN_AVAILABLE = False

        if len(heats) == 14:
            # initialize data for each pilot in the final
            slots = rhapi.db.slots_by_heat(heats[-1].id)
            winners = {}
            for slot in slots:
                pilot_id = slot.pilot_id
                winners[pilot_id] = {
                    "wins": 0,
                    "points": 0
                }

            winners_names = []
            RACE_IS_OVER = False

            # extract rounds from the final
            races = rhapi.db.races_by_heat(heats[-1].id)
            for race_number, race in enumerate(races):
                race_result = rhapi.db.race_results(race)

                if race_result:
                    heat_leaderboard = race_result[race_result['meta']['primary_leaderboard']]
                    winner_pilot_id = heat_leaderboard[0]['pilot_id']

                    if race_number == 0 and IS_IRON_MAN_AVAILABLE and winner_pilot_id == tq_pilot_id:
                        # race is over (Iron Man)
                        leaderboard[0] = build_leaderboard_object(rhapi, 1, heats, 14, 1, "CTA [1] [1]")
                        leaderboard[1] = build_leaderboard_object(rhapi, 2, heats, 14, 2, "[2] [2]")
                        leaderboard[2] = build_leaderboard_object(rhapi, 3, heats, 14, 3, "[3] [3]")
                        leaderboard[3] = build_leaderboard_object(rhapi, 4, heats, 14, 4, "[4] [4]")
                        rhapi.ui.message_alert(rhapi.__('Iron Man Winner: {}').format(leaderboard[0]['callsign']))
                        RACE_IS_OVER = True
                        break

                    winners[winner_pilot_id]["wins"] += 1
                    winners_names.append(rhapi.db.pilot_by_id(winner_pilot_id).display_callsign)

                    winners[heat_leaderboard[0]['pilot_id']]["points"] += 1
                    winners[heat_leaderboard[1]['pilot_id']]["points"] += 2
                    winners[heat_leaderboard[2]['pilot_id']]["points"] += 3
                    winners[heat_leaderboard[3]['pilot_id']]["points"] += 4

                    RACE_IS_OVER = False
                    for pilot_id in winners:
                        if winners[pilot_id]["wins"] > 1:
                            # race is over (Chase the Ace)
                            RACE_IS_OVER = True
                            break
                    if RACE_IS_OVER:
                        # positions from second to fourth are point based
                        # in case of a tie, the result of the latest heat is considered
                        # the smartest way to implement this is take the leaderboard of the last heat and order it by points using Bubblesort as sorting algorithm
                        # it makes sense because Bubblesort does not alter the order of items that are equal 
                        # and it is efficient since we have to order only three elements :)
                        if winners[heat_leaderboard[1]['pilot_id']]["points"] > winners[heat_leaderboard[2]['pilot_id']]["points"]:
                            heat_leaderboard[1], heat_leaderboard[2] = heat_leaderboard[2], heat_leaderboard[1]
                        if winners[heat_leaderboard[2]['pilot_id']]["points"] > winners[heat_leaderboard[3]['pilot_id']]["points"]:
                            heat_leaderboard[2], heat_leaderboard[3] = heat_leaderboard[3], heat_leaderboard[2]
                        if winners[heat_leaderboard[1]['pilot_id']]["points"] > winners[heat_leaderboard[2]['pilot_id']]["points"]:
                            heat_leaderboard[1], heat_leaderboard[2] = heat_leaderboard[2], heat_leaderboard[1]
                        if winners[heat_leaderboard[2]['pilot_id']]["points"] > winners[heat_leaderboard[3]['pilot_id']]["points"]:
                            heat_leaderboard[2], heat_leaderboard[3] = heat_leaderboard[3], heat_leaderboard[2]

                        leaderboard[0] = build_leaderboard_object_basic(rhapi, 1, heat_leaderboard[0], f"CTA [{winners[heat_leaderboard[0]['pilot_id']]['points']}] [1]")
                        leaderboard[1] = build_leaderboard_object_basic(rhapi, 2, heat_leaderboard[1], f"[{winners[heat_leaderboard[1]['pilot_id']]['points']}] [2]")
                        leaderboard[2] = build_leaderboard_object_basic(rhapi, 3, heat_leaderboard[2], f"[{winners[heat_leaderboard[2]['pilot_id']]['points']}] [3]")
                        leaderboard[3] = build_leaderboard_object_basic(rhapi, 4, heat_leaderboard[3], f"[{winners[heat_leaderboard[3]['pilot_id']]['points']}] [4]")

                        rhapi.ui.message_alert(rhapi.__('Chase the Ace Winner: {}').format(leaderboard[0]['callsign']))

                        break

            if not RACE_IS_OVER and len(winners_names) > 0:
                rhapi.ui.message_notify(rhapi.__('Wins: {}').format(', '.join(winners_names)))
    else:
        # if CTA is disabled, just use the results of heat 14
        leaderboard[0] = build_leaderboard_object(rhapi, 1, heats, 14, 1, "1° in Heat 14")
        leaderboard[1] = build_leaderboard_object(rhapi, 2, heats, 14, 2, "2° in Heat 14")
        leaderboard[2] = build_leaderboard_object(rhapi, 3, heats, 14, 3, "3° in Heat 14")
        leaderboard[3] = build_leaderboard_object(rhapi, 4, heats, 14, 4, "4° in Heat 14")

    """ remove empty slots """
    leaderboard = list(filter(lambda x: x != None, leaderboard))

    meta = {
        'rank_fields': [{
            'name': 'result',
            'label': 'Result'
        }]
    }

    return leaderboard, meta

####################################################################################################



def register_handlers(rhapi, args):
    classes = rhapi.db.raceclasses
    options = []
    for this_class in classes:
        if not this_class.name:
            name = f"Class {this_class.id}"
        else:
            name = this_class.name
        options.append(UIFieldSelectOption(this_class.id, name))
    if len(options) > 0:
        default_class = options[0].value
    else:
        default_class = 0

    args['register_fn'](
        RaceClassRankMethod(
            "Brackets",
            brackets,
            {
                'bracket_type': "MultiGP",
                'qualifier_class': default_class,
                'chase_the_ace': True,
                'iron_man': True,
            },
            [
                UIField('bracket_type',
                    "Bracket type",
                    UIFieldType.SELECT,
                    options=[UIFieldSelectOption("MultiGP", "MultiGP")],
                    value="MultiGP",
                    desc="Currently only MultiGP brackets are supported"),
                UIField('qualifier_class',
                    "Qualifier class",
                    UIFieldType.SELECT,
                    options=options,
                    value=default_class,
                    desc="Class used in qualification stage"),
                UIField('chase_the_ace',
                    "Chase the Ace",
                    UIFieldType.CHECKBOX,
                    value=True,
                    desc="Apply the Chase the Ace format in the final heat"),
                UIField('iron_man',
                    "Iron Man rule",
                    UIFieldType.CHECKBOX,
                    value=True,
                    desc="Apply the Iron Man rule in the final heat (CTA is required)"),
            ]
        )
    )

def initialize(rhapi):
    rhapi.events.on(Evt.CLASS_RANK_INITIALIZE, lambda args: register_handlers(rhapi, args))
