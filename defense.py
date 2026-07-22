# defense.py

import requests
import json

def parse_fielding(gameID, is_json=True):
    game = gameID
    if not is_json:
        game = requests.get(f"https://mmolb.com/api/game/{gameID}").json()

    fielding_pass = ["flies out", "force out", "pops out", "grounds out", "lines out", "into a double play"]
    fielding_fail = ["throwing error", "fielding error", "singles on", "doubles on", "triples on"]
    hit_identifier = ["line drive", "fly ball", "ground ball", "popup"]
    hit_code_tag = ["line_drive", "fly_ball", "ground_ball", "pop_up"]
    field_locations = {"the catcher": "C",
                    "first base": "1B",
                    "second base": "2B",
                    "third base": "3B",
                    "the shortstop": "SS",
                    "left field": "LF",
                    "center field": "CF",
                    "right field": "RF",
                    "the pitcher": "P"
                    }

    rosters = {}
    discovered_ids = []
    # first pass's goal: deduce the position of all players
    # key: ingame name. values: position, id
    # REASONING: there can be multiple pitchers almost every game so position keys fail, so name keys it is
    # PROBLEM: this methodology falls apart if a team has two players with the same exact name
    # SOLUTION: pray
    currently_pitching = "home"
    for e in game["EventLog"]:
        # print("looking at event:", e["message"])
        if e["event"] == "AwayLineup":
            away_roster = [_[3:] for _ in e["message"].split("<br>") if "Manager" not in _ and len(_) > 3]
            for _ in range(len(away_roster)):
                away_roster[_] = [away_roster[_][:away_roster[_].find(" ")], away_roster[_][(away_roster[_].find(" ") + 1):]]
            rosters["away"] = {}
            for _ in away_roster:
                rosters["away"][_[1]] = {}
                rosters["away"][_[1]]["position"] = _[0]
        if e["event"] == "HomeLineup":
            home_roster = [_[3:] for _ in e["message"].split("<br>") if "Manager" not in _ and len(_) > 3]
            for _ in range(len(home_roster)):
                home_roster[_] = [home_roster[_][:home_roster[_].find(" ")], home_roster[_][(home_roster[_].find(" ") + 1):]]
            rosters["home"] = {}
            for _ in home_roster:
                rosters["home"][_[1]] = {}
                rosters["home"][_[1]]["position"] = _[0]
        if "the bottom of the" in e["message"]:
            currently_pitching = "away"
        if "the top of the" in e["message"]:
            currently_pitching = "home"
        if e["batter"] != None and e["batter"]["name"] != None and e["batter"]["id"] not in discovered_ids:
            if e["batter"]["name"] in rosters["away"].keys():
                rosters["away"][e["batter"]["name"]]["id"] = e["batter"]["id"]
            if e["batter"]["name"] in rosters["home"].keys():
                rosters["home"][e["batter"]["name"]]["id"] = e["batter"]["id"]
        if e["pitcher"] != None and e["pitcher"]["name"] != None and len(e["pitcher"]["name"]) > 3 and e["pitcher"]["id"] not in discovered_ids:
            rosters[currently_pitching][e["pitcher"]["name"]] = {}
            rosters[currently_pitching][e["pitcher"]["name"]]["position"] = "P"
            rosters[currently_pitching][e["pitcher"]["name"]]["id"] = e["pitcher"]["id"]

    # second pass's goal: judge every fielding call in the game
    prev_message = ""
    stats = {}
    for e in game["EventLog"]:
        if e["event"] == "Field":
            # print(prev_message)
            # print(e["message"])
            
            fielding_result = "N/A"
            if any(term in e["message"] for term in fielding_pass):
                fielding_result = "PASS"
            if any(term in e["message"] for term in fielding_fail):
                fielding_result = "FAIL"
            fielders_list = []
            if e["batter"]["name"] in rosters["away"].keys():
                fielders_list = rosters["home"].keys()
            else:
                fielders_list = rosters["away"].keys()
            players_involved = sorted(
                [name for name in fielders_list if name in e["message"]],
                key=lambda name: e["message"].index(name)
            )
            hit_type = [term for term in hit_identifier if term in prev_message]
            fielding_location = [field_locations[term] for term in field_locations.keys() if term in prev_message]

            if len(players_involved) > 0:
                # print("result:", fielding_result, "| hit type:", hit_type[0], "| player responsible:", players_involved)
                fielder_role = ""
                fielder_id = ""
                if players_involved[0] in rosters["home"].keys():
                    fielder_role = rosters["home"][players_involved[0]]["position"]
                    fielder_id = rosters["home"][players_involved[0]]["id"]
                if players_involved[0] in rosters["away"].keys():
                    fielder_role = rosters["away"][players_involved[0]]["position"]
                    fielder_id = rosters["away"][players_involved[0]]["id"]
                # print("fielding_location:", fielding_location[0], "| fielder_role:", fielder_role)
                if fielding_location[0] == fielder_role: # currently we don't care about unexpected fielders and those are discarded
                    field = hit_code_tag[hit_identifier.index(hit_type[0])] + "_" + ("fielded" if fielding_result == "PASS" else "allowed")
                    # print(f"result: stats[{players_involved[0]}][{field}] += 1")
                    if fielder_id not in stats.keys():
                        stats[fielder_id] = {}
                    if field not in stats[fielder_id].keys():
                        stats[fielder_id][field] = 0
                    stats[fielder_id][field] += 1
            # print("")
        prev_message = e["message"]
    for i in stats:
        # print(i, stats[i])
        pass
    return stats

# test = requests.get(f"https://mmolb.com/api/game/69f8c2b0fdf9f818839d06d7").json()
# parse_fielding(test)