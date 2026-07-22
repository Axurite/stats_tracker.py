# defense.py

import requests
import json

def parse_fielding(gameID, is_json=True):
    game = gameID

    if not is_json:
        game = requests.get(
            f"https://mmolb.com/api/game/{gameID}",
            timeout=30
        ).json()

    fielding_pass = [
        "flies out",
        "force out",
        "pops out",
        "grounds out",
        "lines out",
        "into a double play",
    ]

    fielding_fail = [
        "throwing error",
        "fielding error",
        "singles on",
        "doubles on",
        "triples on",
    ]

    hit_identifier = [
        "line drive",
        "fly ball",
        "ground ball",
        "popup",
    ]

    hit_code_tag = [
        "line_drive",
        "fly_ball",
        "ground_ball",
        "pop_up",
    ]

    field_locations = {
        "the catcher": "C",
        "first base": "1B",
        "second base": "2B",
        "third base": "3B",
        "the shortstop": "SS",
        "left field": "LF",
        "center field": "CF",
        "right field": "RF",
        "the pitcher": "P",
    }

    rosters = {
        "away": {},
        "home": {},
    }

    discovered_ids = set()

    # First pass:
    # Parse the lineups and attach IDs to players when they appear as
    # batters or pitchers.
    currently_pitching = "home"

    for e in game.get("EventLog", []):
        message = e.get("message") or ""

        if e.get("event") == "AwayLineup":
            away_roster = [
                line[3:]
                for line in message.split("<br>")
                if "Manager" not in line and len(line) > 3
            ]

            rosters["away"] = {}

            for player_line in away_roster:
                first_space = player_line.find(" ")

                if first_space == -1:
                    continue

                position = player_line[:first_space]
                name = player_line[first_space + 1:]

                rosters["away"][name] = {
                    "position": position,
                }

        if e.get("event") == "HomeLineup":
            home_roster = [
                line[3:]
                for line in message.split("<br>")
                if "Manager" not in line and len(line) > 3
            ]

            rosters["home"] = {}

            for player_line in home_roster:
                first_space = player_line.find(" ")

                if first_space == -1:
                    continue

                position = player_line[:first_space]
                name = player_line[first_space + 1:]

                rosters["home"][name] = {
                    "position": position,
                }

        if "the bottom of the" in message:
            currently_pitching = "away"

        if "the top of the" in message:
            currently_pitching = "home"

        batter = e.get("batter")

        if (
            batter is not None
            and batter.get("name") is not None
            and batter.get("id") is not None
        ):
            batter_name = batter["name"]
            batter_id = batter["id"]

            if batter_name in rosters["away"]:
                rosters["away"][batter_name]["id"] = batter_id

            if batter_name in rosters["home"]:
                rosters["home"][batter_name]["id"] = batter_id

            discovered_ids.add(batter_id)

        pitcher = e.get("pitcher")

        if (
            pitcher is not None
            and pitcher.get("name") is not None
            and pitcher.get("id") is not None
            and len(pitcher["name"]) > 3
        ):
            pitcher_name = pitcher["name"]
            pitcher_id = pitcher["id"]

            if pitcher_id not in discovered_ids:
                rosters[currently_pitching][pitcher_name] = {
                    "position": "P",
                    "id": pitcher_id,
                }

                discovered_ids.add(pitcher_id)

    # Second pass:
    # Judge each fielding call.
    prev_message = ""
    stats = {}

    for e in game.get("EventLog", []):
        message = e.get("message") or ""

        if e.get("event") == "Field":
            fielding_result = None

            if any(term in message for term in fielding_pass):
                fielding_result = "PASS"

            if any(term in message for term in fielding_fail):
                fielding_result = "FAIL"

            # Ignore field events that do not match either category.
            if fielding_result is None:
                prev_message = message
                continue

            # Do not use e["batter"] here.
            #
            # On Field events, the API may already have advanced the batter
            # object to the next hitter, while the message still describes
            # the previous hitter's play.
            #
            # inning_side 0 = top of inning, so home team is fielding.
            # inning_side 1 = bottom of inning, so away team is fielding.
            inning_side = e.get("inning_side")

            if inning_side == 0:
                fielding_team = "home"
            elif inning_side == 1:
                fielding_team = "away"
            else:
                print("\nUNKNOWN INNING SIDE")
                print("Field event:", json.dumps(e, indent=2))
                prev_message = message
                continue

            fielders = rosters[fielding_team]

            players_involved = sorted(
                [
                    name
                    for name in fielders
                    if name in message
                ],
                key=lambda name: message.index(name),
            )

            hit_type = [
                term
                for term in hit_identifier
                if term in prev_message
            ]

            fielding_location = [
                field_locations[term]
                for term in field_locations
                if term in prev_message
            ]

            if not players_involved:
                prev_message = message
                continue

            if not hit_type:
                print("\nUNKNOWN HIT TYPE")
                print("Field message:", message)
                print("Previous message:", prev_message)
                prev_message = message
                continue

            if not fielding_location:
                print("\nUNKNOWN FIELDING LOCATION")
                print("Field message:", message)
                print("Previous message:", prev_message)
                prev_message = message
                continue

            player_name = players_involved[0]
            player_data = fielders[player_name]

            if "id" not in player_data:
                print("\nMISSING FIELDER ID")
                print("Fielding team:", fielding_team)
                print("Player:", player_name)
                print("Roster entry:", player_data)
                print("Players involved:", players_involved)
                print("Field event:", json.dumps(e, indent=2))
                print("Previous message:", prev_message)
                print(
                    "Relevant roster:",
                    json.dumps(fielders, indent=2),
                )

                # Skip the event instead of losing the entire processing run.
                prev_message = message
                continue

            fielder_role = player_data["position"]
            fielder_id = player_data["id"]

            expected_location = fielding_location[0]
            current_hit_type = hit_type[0]

            # Ignore plays handled by an unexpected position, preserving
            # the behavior of your original parser.
            if expected_location != fielder_role:
                prev_message = message
                continue

            hit_code = hit_code_tag[
                hit_identifier.index(current_hit_type)
            ]

            result_code = (
                "fielded"
                if fielding_result == "PASS"
                else "allowed"
            )

            field = f"{hit_code}_{result_code}"

            if fielder_id not in stats:
                stats[fielder_id] = {}

            if field not in stats[fielder_id]:
                stats[fielder_id][field] = 0

            stats[fielder_id][field] += 1

        prev_message = message

    return stats

# test = requests.get(f"https://mmolb.com/api/game/69f8c2b0fdf9f818839d06d7").json()
# parse_fielding(test)