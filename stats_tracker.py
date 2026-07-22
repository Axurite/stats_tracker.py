import requests
import json
import os
import defense
import stats_config as config
from contextlib import chdir


def update_rosters(quick=False):
    leagues = [config.valid_options()["leagues"][i] for i in config.get_config()["leagues"]]
    player_dict = {}
    team_dict = {}
    league_dict = {}
    quick_team_dict = []
    if quick:
        if os.path.isfile("data/roster_info.json"):
            with open("data/roster_info.json", "r") as f:
                roster_info = json.load(f)
                quick_team_dict = [i for i in roster_info["teams"].keys()]
        else:
            print("quick roster update can't be done before a normal one, doing a normal roster update")
            quick = False
    for l in leagues:
        league = requests.get(f"https://mmolb.com/api/league/{l}").json()
        for t in league["Teams"]:
            if not quick or t in quick_team_dict:
                team = requests.get(f"https://mmolb.com/api/team/{t}").json()
                if team["Record"]["Regular Season"]["Losses"] + team["Record"]["Regular Season"]["Wins"] > 0: # we only care about active teams
                    print(f"Fetching team info: {team["Location"]} {team["Name"]}")
                    members = []
                    for p in team["Players"]: # write down all the players
                        if p["PlayerID"] != "#": # we'll discard empty slots, who all have the ID of "#"
                            designated_hitter = False
                            for i in members:
                                if player_dict[i]["position"] == p["Position"] and p["Position"] not in ["SP", "RP"]:
                                    designated_hitter = True
                            if designated_hitter:
                                player_dict[p["PlayerID"]] = {"name": f"{p["FirstName"]} {p["LastName"]}", "position": "DH", "team": f"{t}", "bench": False}
                            else:
                                player_dict[p["PlayerID"]] = {"name": f"{p["FirstName"]} {p["LastName"]}", "position": f"{p["Position"]}", "team": f"{t}", "bench": False}
                            members.append(p["PlayerID"])
                    for p in team["Bench"]: # batter and pitcher
                        for k in team["Bench"][p]: # 1 2 3 and 4
                            if k["PlayerID"] != "#":
                                player_dict[k["PlayerID"]] = {"name": f"{k["FirstName"]} {k["LastName"]}", "position": k["Slot"], "team": f"{t}", "bench": True}
                                members.append(k["PlayerID"])
                            
                    # write down some information about the team
                    team_dict[t] = {"league": l, 
                                    "emoji": team["Emoji"], 
                                    "name": f"{team["Location"]} {team["Name"]}", 
                                    "members": members, 
                                    "wins": team["Record"]["Regular Season"]["Wins"], 
                                    "losses": team["Record"]["Regular Season"]["Losses"], 
                                    "rd": team["Record"]["Regular Season"]["RunDifferential"]}
        league_dict[l] = league["Teams"]
    roster_info_dict = {"players": player_dict, "teams": team_dict, "leagues": league_dict}
    with open("data/roster_info.json", "w") as f:
        json.dump(roster_info_dict, f)
        f.close()

# gather data you need to go to individual player IDs to obtain
def update_rosters_deep():
    roster_info = {}
    if os.path.isfile("data/roster_info.json"):
        with open("data/roster_info.json", "r") as f:
            roster_info = json.load(f)
            counter = 0
            to_check = len(roster_info["players"].keys())
            for i in roster_info["players"].keys():
                player = requests.get(f"https://mmolb.com/api/player/{i}").json()
                counter += 1
                print(f"\r\033[KFetching individual player info \033[38;5;239m[{counter:>{len(str(to_check))}}/{to_check:>{len(str(to_check))}} {roster_info["teams"][roster_info["players"][i]["team"]]["emoji"]} {roster_info["players"][i]["name"]:<35}]\033[0m", end="")
                # obtain effective level
                eff_level = 1 + len(player["AugmentHistory"])
                if "AppliedLevelUps" in player.keys():
                    eff_level += len(player["AppliedLevelUps"])
                roster_info["players"][i]["effective_level"] = eff_level
                # obtain the hand they use to throw
                roster_info["players"][i]["throws"] = player["Throws"]
                
                # obtain the sum of tiers on the player's items
                drip_score = 0
                for j in player["Equipment"].keys():
                    if player["Equipment"][j] != None:
                        for k in player["Equipment"][j]["Effects"]:
                            drip_score += k["Tier"]
                roster_info["players"][i]["drip_score"] = drip_score

        with open("data/roster_info.json", "w") as f:
            json.dump(roster_info, f)
        print(f"\r\033[KFetching individual player info [done!]")

# update the game list
def update_games(s, hard_reset=False):
    # 1. get the games already in the database
    checked_games = []
    raw_stuff = {}
    start_search_from = 0 # the day we start searching from
    if os.path.isfile("data/all_games.txt"):
        f = open("data/all_games.txt", "r", encoding="utf-8")
        for line in f:
            start_search_from = int(line.strip().split(",")[3]) - 1
            if int(line.strip().split(",")[3]) not in raw_stuff.keys(): # this helps us skip scraped days in the next step
                raw_stuff[int(line.strip().split(",")[3])] = [] # O(n) doesn't seem better than O(n^2) until n = 300 lol
            raw_stuff[int(line.strip().split(",")[3])].append(line.strip())
            if line.strip().split(",")[5] == "1": # this is the flag for checked games
                checked_games.append(line.strip().split(",")[0])
        f.close()

    # 2. get new games (preserve the flag while that happens)
    game_log = open("data/all_games.txt", "w", encoding="utf-8")
    season = requests.get(f"https://mmolb.com/api/season/{s}").json()
    day_counter = 0
    print(f"Searching for new games...")
    for d in season["Days"]:
        day_counter += 1
        if day_counter < start_search_from: # if the day already passed and the database already has content, there is no new days. saves some api calls
            if day_counter in raw_stuff.keys():
                for i in raw_stuff[day_counter]:
                    game_log.write(f"{i}\n")
        else:
            day = requests.get(f"https://mmolb.com/api/day/{d}").json()
            if day["Season"] != 11 or day["Day"] != 2: # this is to exclusively discard data from the outlier day of s11 d2
                # print(f"Fetching games played on Season {season["Season"]} Day {day["Day"]}...")
                stop_early_flag = True
                for g in day["Games"]:
                    stop_early_flag = False
                    if g["GameID"] != "#":
                        # game ID, away team ID, home team ID, day, complete or not, parsed by my program or not
                        if g["GameID"] in checked_games and (not hard_reset):
                            game_log.write(f"{g["GameID"]},{g["AwayTeamID"]},{g["HomeTeamID"]},{day["Day"]},{g["State"]},1\n")
                        else:
                            game_log.write(f"{g["GameID"]},{g["AwayTeamID"]},{g["HomeTeamID"]},{day["Day"]},{g["State"]},0\n")
                if (stop_early_flag or day["Day"] == 240) and True:
                    # print(f"Fetching concluded at Season {season["Season"]} Day {day["Day"]}")
                    break
    game_log.close()

# add data from unrecorded games to the player_data.json file
def record_games(toi = None, hard_reset = False):
    f = open("data/all_games.txt", "r", encoding="utf-8")
    games = []
    for line in f:
        games.append(line.strip().split(","))
    f.close()
    
    players = {}

    if os.path.isfile("data/player_data.json") and (not hard_reset):
        with open("data/player_data.json", "r") as f:
            players = json.load(f)
            

    count_tornado = 0
    count_all = 0 # this variable is nasty and should be removed posthaste
    for i in games:
        # first is obvious, i[5] == 0 makes sure to avoid double-counting data, final one skips games we don't care about rn
        if i[4] == "Complete" and i[5] == "0" and (toi == None or (i[1] in toi or i[2] in toi)):
            count_tornado += 1
            game = requests.get(f"https://mmolb.com/api/game/{i[0]}").json()

            # tick up data from the game being examined
            away_victory = game["EventLog"][-1]["away_score"] > game["EventLog"][-1]["home_score"]
            print(f"Processing game: {i[0]} | S{game["Season"]} D{game["Day"]:<3} | \033[38;5;{157 if away_victory else 217}m{game["AwayTeamName"]}\x1b[0m vs. \033[38;5;{217 if away_victory else 157}m{game["HomeTeamName"]}\x1b[0m")
            for t in game["Stats"]: # team
                for p in game["Stats"][t]: # player
                    if p not in players:
                        players[p] = {}
                    for stat in game["Stats"][t][p]:
                        if stat not in players[p]:
                            players[p][stat] = game["Stats"][t][p][stat]
                        else:
                            players[p][stat] += game["Stats"][t][p][stat]
            # TODO: hypothetical defense tracking goes here
            # import defense, call a function that returns a package that looks exactly like the API stats dictionary
            defense_stats = defense.parse_fielding(game)
            for p in defense_stats:
                if p not in players:
                    players[p] = {}
                for stat in defense_stats[p]:
                    if stat not in players[p]:
                        players[p][stat] = defense_stats[p][stat]
                    else:
                        players[p][stat] += defense_stats[p][stat]
            # then ingest it as usual
            for e in game["EventLog"]:
                if e["event"] == "Pitch":
                    pitch = "".join(e["pitch_info"].strip().split()[1:])
                    zone = e["zone"]
                    if "pitch_data" not in players[e["pitcher"]["id"]]:
                        players[e["pitcher"]["id"]]["pitch_data"] = {}
                    if pitch not in players[e["pitcher"]["id"]]["pitch_data"]:
                        players[e["pitcher"]["id"]]["pitch_data"][pitch] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "11": 0, "12": 0, "13": 0, "14": 0}
                    players[e["pitcher"]["id"]]["pitch_data"][pitch][str(zone)] += 1
                
            games[count_all][5] = "1"
        count_all += 1
    
    # change game list to reflect the now recorded games:
    f = open("data/all_games.txt", "w", encoding="utf-8")
    for i in games:
        f.write(f"{",".join(i)}\n")
    f.close()

    with open("data/player_data.json", "w") as f:
        json.dump(players, f)

# create a json that stores common human metrics for players
def calculate_human_stats():
    players = {}
    if os.path.isfile("data/player_data.json"):
        with open("data/player_data.json", "r") as f:
            players = json.load(f)
            f.close()
    full_result = {}
    for p in players:
        good_shit = {"at_bats": 0,
                     "plate_appearances": 0,
                     "singles": 0,
                     "doubles": 0,
                     "triples": 0,
                     "home_runs": 0,
                     "walked": 0,
                     "hit_by_pitch": 0,
                     "sac_flies": 0,
                     "ground_ball_fielded": 0,
                     "ground_ball_allowed": 0,
                     "fly_ball_fielded": 0,
                     "fly_ball_allowed": 0,
                     "line_drive_fielded": 0,
                     "line_drive_allowed": 0,
                     "outs": 0, # pitcher
                     "earned_runs": 0, # pitcher
                     "strikeouts": 0, # pitcher
                     "struck_out": 0, 
                     "hits_allowed": 0, # pitcher
                     "walks": 0, # pitcher
                     "home_runs_allowed": 0} # pitcher
        result = {}
        for stat in good_shit:
            if stat in players[p]:
                good_shit[stat] = players[p][stat]
        if good_shit["at_bats"] > 0:
            hits = good_shit["singles"] + good_shit["doubles"] + good_shit["triples"] + good_shit["home_runs"]
            result["AVG"] = hits / good_shit["at_bats"]
            result["OBP"] = (hits + good_shit["walked"] + good_shit["hit_by_pitch"]) / (good_shit["at_bats"] + good_shit["walked"] + good_shit["hit_by_pitch"] + good_shit["sac_flies"])
            result["SLG"] = (good_shit["singles"] + 2 * good_shit["doubles"] + 3 * good_shit["triples"] + 4 * good_shit["home_runs"]) / good_shit["at_bats"]
            result["OPS"] = result["OBP"] + result["SLG"]
            result["K%"] = good_shit["struck_out"] / good_shit["plate_appearances"]
        if good_shit["outs"] > 0:
            result["ERA"] = good_shit["earned_runs"] / (good_shit["outs"] / 27)
            result["WHIP"] = (good_shit["walks"] + good_shit["hits_allowed"]) / (good_shit["outs"] / 3)
            result["K/9"] = good_shit["strikeouts"] / (good_shit["outs"] / 27)
            result["BB/9"] = good_shit["walks"] / (good_shit["outs"] / 27)
            result["H/9"] = good_shit["hits_allowed"] / (good_shit["outs"] / 27)
            result["HR/9"] = good_shit["home_runs_allowed"] / (good_shit["outs"] / 27)
        if good_shit["ground_ball_fielded"] + good_shit["ground_ball_allowed"] > 0:
            result["GBO%"] = good_shit["ground_ball_fielded"] / (good_shit["ground_ball_fielded"] + good_shit["ground_ball_allowed"])
        if good_shit["fly_ball_fielded"] + good_shit["fly_ball_allowed"] > 0:
            result["FBO%"] = good_shit["fly_ball_fielded"] / (good_shit["fly_ball_fielded"] + good_shit["fly_ball_allowed"])
        if good_shit["line_drive_fielded"] + good_shit["line_drive_allowed"] > 0:
            result["LDO%"] = good_shit["line_drive_fielded"] / (good_shit["line_drive_fielded"] + good_shit["line_drive_allowed"])
        full_result[p] = result
    with open("data/processed_player_data.json", "w") as f:
        json.dump(full_result, f)
        f.close()

# calculate 100 thresholds for each calculated human stat and stores them in stat_barriers
def calculate_percentiles():
    barriers = {}
    players = {}
    rosters = {} # we want to have this so that we potentially exclude people who are not recognized by the program
    if os.path.isfile("data/player_data.json"):
        with open("data/player_data.json", "r") as f:
            players = json.load(f)
    if os.path.isfile("data/roster_info.json"):
        with open("data/roster_info.json", "r") as f:
            rosters = json.load(f)
            rosters = [_ for _ in rosters["players"].keys()]

    at_bats, outs = thresholds()

    for stat in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP", "K%", "K/9", "BB/9", "H/9", "HR/9", "GBO%", "FBO%", "LDO%"]:
        lower_better = False
        pitching_stat = False
        if stat in ["ERA", "WHIP", "K%", "BB/9", "H/9", "HR/9"]:
            lower_better = True
        if stat in ["ERA", "WHIP", "K/9", "BB/9", "H/9", "HR/9"]:
            pitching_stat = True
        numbers = {}
        if os.path.isfile("data/processed_player_data.json"):
            with open("data/processed_player_data.json", "r") as f:
                numbers = json.load(f)
        everyone = []
        for i in numbers:
            if stat in numbers[i] and ((pitching_stat and players[i]["outs"] > outs) or ("at_bats" in players[i] and players[i]["at_bats"] > at_bats)) and i in rosters:
                everyone.append(numbers[i][stat])
        everyone.sort(key=lambda x: x, reverse=lower_better)
        results = []
        for i in range(100):
            results.append(everyone[int((len(everyone) * i / 100))])
        # print(results)
        barriers[stat] = results
    with open("data/stat_barriers.json", "w") as f:
        json.dump(barriers, f)

# return the ansi string that will color a piece of text in the console
def color(stat, value):
    lower_better = False
    pitching_stat = False
    if stat in ["ERA", "WHIP", "K%", "BB/9", "H/9", "HR/9"]:
        lower_better = True
    if stat in ["ERA", "WHIP", "K/9", "BB/9", "H/9", "HR/9"]:
        pitching_stat = True
    
    barriers = []
    with open("data/stat_barriers.json", "r") as f:
        barriers = json.load(f)
    percentile = 0
    for i in range(100):
        if not lower_better:
            if value < barriers[stat][i]:
                break
        else:
            if value > barriers[stat][i]:
                break
        percentile += 1
    ans = 0
    if percentile < 10:
        ans = 161
    elif percentile < 30:
        ans = 208
    elif percentile < 70:
        ans = 220
    elif percentile < 90:
        ans = 77
    elif percentile < 99:
        ans = 33
    else:
        ans = "92m\033[1"
    return f"\033[38;5;{ans}m"
    # 208, 216, 231, 105, 33, 92

# return the minimum numbers of ABs or outs to qualify a player for the stat leaderboards
def thresholds():
    players = {}
    if os.path.isfile("data/player_data.json"):
        with open("data/player_data.json", "r") as f:
            players = json.load(f)
    at_bats = []
    outs = []
    for i in players:
        if "at_bats" in players[i]:
            at_bats.append(players[i]["at_bats"])
        if "outs" in players[i]:
            outs.append(players[i]["outs"])
    at_bats.sort()
    outs.sort()
    # SEASON 13 MODIFICATION: Due to Flood weather, benchies now technically play and make the at-bat percentages
    # plummit. We're going to be shifting this from eliminating the bottom 15% to eliminating the bottom 30%
    # at_bats = at_bats[int((len(at_bats) * 0.30) // 1)]
    # outs = outs[int((len(outs) * 0.35) // 1)]
    at_bats = at_bats[-1] // 2.5 # 07/10/2026: i changed the thresholds to be a fraction of the leader instead of a percentile
    outs = outs[-1] // 2.5 #                   the idea is that the leader's always a regular, so we only want someone who's pitched a % of the regular
    return at_bats, outs

# print the leaderboards for a specific stat (though it prints all relevant stats, it sorts by the specified one)
# "reverse" argument makes it so the worst players show up
# "no_qualify" removes the AB/out limit
def leaderboard(stat, reverse=False, no_qualify=False, include_unknown_players=False):
    stat = stat.upper()
    numbers = {}
    if os.path.isfile("data/processed_player_data.json"):
        with open("data/processed_player_data.json", "r") as f:
            numbers = json.load(f)
    qual_check = {}
    if os.path.isfile("data/player_data.json"):
        with open("data/player_data.json", "r") as f:
            qual_check = json.load(f)
    at_bats, outs = thresholds()
    # if "all" is enabled, we no longer cared about the barriers
    at_bats = 1 if no_qualify else at_bats
    outs = 1 if no_qualify else outs
    roster_info = {}
    if os.path.isfile("data/roster_info.json"):
        with open("data/roster_info.json", "r") as f:
            roster_info = json.load(f)
    registered_players = [_ for _ in roster_info["players"].keys()]

    leaderboard = []
    lower_better = False
    pitching_stat = False
    defense_stat = False
    if stat in ["ERA", "WHIP", "K%", "BB/9", "H/9", "HR/9"]:
        lower_better = True
    if stat in ["ERA", "WHIP", "K/9", "BB/9", "H/9", "HR/9"]:
        pitching_stat = True
    if stat in ["GBO%", "LDO%", "FBO%"]:
        defense_stat = True
        print("NOTE: defense thresholds are currently a work in progress (current criteria is 20)")
    if pitching_stat:
        print("Required outs:", outs)
    else:
        print("Required ABs:", at_bats)
    if stat not in ["ERA", "WHIP", "K/9", "AVG", "OBP", "SLG", "OPS", "K%", "BB/9", "H/9", "HR/9", "GBO%", "LDO%", "FBO%"]:
        print(f"Stat {stat} not recognized")
        return -1

    for i in numbers:
        if i in registered_players or include_unknown_players:
            if pitching_stat:
                if "outs" in qual_check[i] and qual_check[i]["outs"] > outs:
                    leaderboard.append([i, numbers[i][stat]])
            elif defense_stat:
                
                if "outs" not in qual_check[i] or qual_check[i]["outs"] < 3: # the "WE HATE PITCHERS" line that excludes pitchers from defense leaderboards
                    defense = ["ground_ball_allowed", "ground_ball_fielded", "fly_ball_allowed", "fly_ball_fielded", "line_drive_allowed", "line_drive_fielded"]
                    for d in range(len(defense)):
                        defense[d] = qual_check[i][defense[d]] if defense[d] in qual_check[i] else 0
                    if stat == "GBO%" and defense[0] + defense[1] > 20:
                        leaderboard.append([i, numbers[i][stat]])
                    if stat == "FBO%" and defense[2] + defense[3] > 20:
                        leaderboard.append([i, numbers[i][stat]])
                    if stat == "LDO%" and defense[4] + defense[5] > 20:
                        leaderboard.append([i, numbers[i][stat]])
            else:
                if "at_bats" in qual_check[i] and qual_check[i]["at_bats"] > at_bats:
                    leaderboard.append([i, numbers[i][stat]])

    leaderboard.sort(key=lambda x: x[1], reverse=reverse ^ (not lower_better))

    for i in leaderboard[:20]:
        print_overview(i[0], roster_info, numbers, header="emoji")

# print the thresholds for the program to color stats in overviews
def legend():
    strings = []
    with open("data/stat_barriers.json", "r") as f:
        barriers = json.load(f)
        string = " " * 19 + "| "
        for i in barriers.keys():
            string += f"{i:<6} | "
        print(string)
        for i in [[98, "92m\033[1", "Elite   | Top 2%  "], 
                  [90, 33, "Great   | Top 10% "], 
                  [70, 77, "Good    | Top 30% "], 
                  [50, 241, "Median  | Top 50% "],
                  [30, 220, "Average | Top 70% "], 
                  [10, 208, "Bad     | Top 90% "], 
                  [0, 161, "Awful   | Top 100%"]]:
            string = ""
            for j in barriers.keys():
                string += f"{f"\033[38;5;{i[1]}m{f"{barriers[j][i[0]]:.3f}":>6}\x1b[0m | ":<12}"
            print(f"\033[38;5;{i[1]}m{i[2]}\x1b[0m |", string)

# console
def search_program():
    numbers = {}
    if os.path.isfile("data/processed_player_data.json"):
        with open("data/processed_player_data.json", "r") as f:
            numbers = json.load(f)
    roster_info = {}
    if os.path.isfile("data/roster_info.json"):
        with open("data/roster_info.json", "r") as f:
            roster_info = json.load(f)
    prompt = " "
    while prompt.lower() not in ["1", "close", "exit", "cls"]:
        prompt = input("Look up team by ID or name: ")
        flag = False
        # if user entered a name instead of an ID, set the input to be the ID
        if prompt not in roster_info["teams"]: 
            for id in roster_info["teams"]:
                if roster_info["teams"][id]["name"].lower() == prompt.lower():               
                    prompt = id
                    flag = True
                    break
        else:
            flag = True

        if flag:
            print(f"{roster_info["teams"][prompt]["emoji"]} {roster_info["teams"][prompt]["name"]}")
            for m in roster_info["teams"][prompt]["members"]:
                print_overview(m, roster_info, numbers)

        if not flag:
            if prompt == "hard_reset":
                pass
                # current = requests.get("https://mmolb.com/api/seasons").json()["seasons"][0]["season_id"]
                # update_games(current, hard_reset=True)
                # get_league_set = []
                # temp = open("data/all_teams.txt", "r", encoding="utf-8")
                # for t in temp:
                #     if t.strip().split(",")[1] == "6805db0cac48194de3cd3fed":
                #         get_league_set.append(t.strip().split(",")[0])
                # record_games(toi=get_league_set, hard_reset=True)
                # calculate_human_stats()
            elif prompt.lower() == "legend":
                legend()
            elif prompt[:11].lower() == "leaderboard":
                prompt = prompt.split(" ")
                reverse = False
                no_qualify = False
                if len(prompt) > 2:
                    arguments = prompt[2:]
                    reverse = "reverse" in arguments
                    no_qualify = "all" in arguments
                if len(prompt) > 1:
                    leaderboard(prompt[1].upper(), reverse=reverse, no_qualify=no_qualify)
                prompt = "".join(prompt)
            elif prompt[:5].lower() == "debug":
                prompt = prompt.split(" ")
                if len(prompt) > 1:
                    with open("data/player_data.json", "r") as f:
                        nitty_gritty = json.load(f)
                        if prompt[1] in nitty_gritty:
                            print(numbers[prompt[1]])
                            print(dict(sorted(nitty_gritty[prompt[1]].items())))
                        else:
                            print("player not found :(")
                prompt = "" # this is to return it to a string that won't crash the program
            elif prompt[:5].lower() == "pitch":
                prompt = prompt.split(" ")
                if len(prompt) > 1:
                    pitch_breakdown(prompt[1])
                prompt = ""
            elif prompt.lower() == "config":
                if config.edit():
                    print("as the league list has changed the program will now exit; please run again to begin adding new data")
                    print("yes this is kind of stupid. maybe azurite will change it later?")
                    os.remove("data/all_games.txt")
                    os.remove("data/player_data.json")
                    os.remove("data/processed_player_data.json")
                    os.remove("data/roster_info.json")
                    os.remove("data/stat_barriers.json")
                    return
            elif prompt.lower() not in ["1", "close", "exit", "cls"]:
                print("team not found :(")
        print("")

def pitch_breakdown(playerID):
    with open("data/player_data.json", "r") as f, open("data/roster_info.json", "r") as f2:
        nitty_gritty = json.load(f)
        roster_info = json.load(f2)
        global_dist = get_pitch_zone_statistics()
        if "pitch_data" in nitty_gritty[playerID]:
            print(roster_info["players"][playerID]["name"], "-", f"{roster_info["teams"][roster_info["players"][playerID]["team"]]["emoji"]} {f"{roster_info["teams"][roster_info["players"][playerID]["team"]]["name"]}"}")
            for i in nitty_gritty[playerID]["pitch_data"]:
                grid = [[11, 0, 0, 0, 12, 0, -11, 0, 0, 0, -12],
                        [0, 1, 2, 3, 0, 0, 0, -1, -2, -3, 0],
                        [0, 4, 5, 6, 0, 0, 0, -4, -5, -6, 0],
                        [0, 7, 8, 9, 0, 0, 0, -7, -8, -9, 0],
                        [13, 0, 0, 0, 14, 0, -13, 0, 0, 0, -14]]
                print(i, "distribution")
                data = nitty_gritty[playerID]["pitch_data"][i] # this is here to make the code not hyroglyphic
                personal = {}
                everyone = {}
                for j in data.keys():
                    pitch_type = " ".join([roster_info["players"][playerID]["throws"], i])
                    personal[j] = 100 * data[str(j)] / sum([data[l] for l in data.keys()]) # load % of distribution for this player only
                    everyone[j] = 100 * global_dist[pitch_type][str(j)] / sum([global_dist[pitch_type][l] for l in global_dist[pitch_type].keys()]) # load % of distribution for everyone
                for j in grid:
                    to_print = ""
                    for k in j:
                        if k == 0:
                            to_print += f"{"":>5}"
                        if k > 0:
                            to_print += f"\033[38;5;77m" if personal[str(k)] > everyone[str(k)] else f"\033[38;5;161m"
                            if str(k) not in data.keys():
                                to_print += f"{"0.0":>5}"
                            else:
                                to_print += f"{f"{personal[str(k)]:.1f}":>5}"
                            to_print += "\x1b[0m"
                        if k < 0:
                            # print(pitch_type)
                            if str(k * -1) not in global_dist[" ".join([roster_info["players"][playerID]["throws"], i])].keys():
                                to_print += f"{"0.0":>5}"
                            else:
                                # print("hi2")
                                to_print += f"{f"{everyone[str(k * -1)]:.1f}":>5}"
                    print(to_print)

def get_pitch_zone_statistics():
    with open("data/player_data.json", "r") as f, open("data/roster_info.json", "r") as f2:
        nitty_gritty = json.load(f)
        roster_info = json.load(f2)
        counters = {}
        count = 0
        for i in nitty_gritty.keys():
            if "pitch_data" in nitty_gritty[i].keys() and i in roster_info["players"].keys():
                for j in nitty_gritty[i]["pitch_data"]:
                    # print(roster_info["players"][i]["name"], roster_info["players"][i]["throws"], j, nitty_gritty[i]["pitch_data"][j])
                    if "throws" not in roster_info["players"][i].keys():
                        print("pitch zone statistics will be available when you do a deep dive on player info. enter 'd' or 'deep' on the roster update screen to do this")
                        return counters
                    if " ".join([roster_info["players"][i]["throws"], j]) not in counters.keys():
                        counters[" ".join([roster_info["players"][i]["throws"], j])] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0, "11": 0, "12": 0, "13": 0, "14": 0}
                    for k in nitty_gritty[i]["pitch_data"][j].keys():
                        counters[" ".join([roster_info["players"][i]["throws"], j])][k] += nitty_gritty[i]["pitch_data"][j][k]
            count += 1
        return counters

# TODO: hey there's a todo in this function
def print_overview(playerID, roster_info, numbers, header="position"):
    hidden_stats = {"C": ["GBO%", "LDO%", "FBO%"],
                    "1B": ["LDO%", "FBO%"],
                    "2B": ["LDO%", "FBO%"],
                    "3B": ["LDO%", "FBO%"],
                    "SS": ["LDO%", "FBO%"],
                    "LF": ["GBO%"],
                    "CF": ["GBO%"],
                    "RF": ["GBO%"],
                    "DH": ["GBO%", "LDO%", "FBO%"],
                    "SP": ["GBO%", "LDO%", "FBO%"],
                    "RP": ["GBO%", "LDO%", "FBO%"],
                    "CL": ["GBO%", "LDO%", "FBO%"],
                    "B1": [], "B2": [], "B3": [], "B4": [],
                    "P1": [], "P2": [], "P3": [], "P4": []} # this dictionary tells us stats we don't are about (e.g. GBO% for outfielders)
    to_print = ""
    if playerID in roster_info["players"]:
        player_info = roster_info["players"][playerID]
        to_print = f"{"\033[38;5;239m" if player_info["bench"] else ""}{player_info["position"][:2]:>2} {f"{player_info["name"]} \033[38;5;239m{f"{f"({player_info["effective_level"]})" if "effective_level" in player_info.keys() else ""}"}\x1b[0m":<40}"
        if header == "emoji":
            to_print = f"{"\033[38;5;239m" if player_info["bench"] else ""}{roster_info["teams"][roster_info["players"][playerID]["team"]]["emoji"]} {f"{player_info["name"]} \033[38;5;239m{f"{f"({player_info["effective_level"]})" if "effective_level" in player_info.keys() else ""}"}\x1b[0m":<40}"
    else:
        to_print = f"{playerID:<28}" # this is 28 and the other one is offset by 40 because that's the amount of space the coloring takes up
    # print the name
    if playerID in numbers.keys() and playerID in roster_info["players"]:
        for k in numbers[playerID]: # TODO: there's an issue in which players who have not done anything at all (benchies mostly) crash this due to not being in the database
            if k not in hidden_stats[roster_info["players"][playerID]["position"][:2]]: # 07/10/2026: the reason there's a [:2] is because of the SP specification bug
                to_print += f"{k} {color(k, numbers[playerID][k])}{f"{numbers[playerID][k]:.3f}":>6}\x1b[0m | "
    print(to_print)

def all_stars():
    pass
    # batters: min. ???
    # DH:  home runs
    # C:   OBP
    # 1B:  AVG
    # 2B:  OPS
    # 3B:  SLG
    # SS:  RBI
    # LF:  singles
    # CF:  stolen bases
    # RF:  runs
    # ptichers: min. 30 IP sans closers
    # SP1: QS
    # SP2: wins
    # SP3: H/9
    # SP4: K/9
    # SP5: ERA
    # RP1: WHIP
    # RP2: K/BB
    # RP3: worst HR/9
    # CL:  saves
    
with chdir(os.path.dirname(os.path.realpath(__file__))):
    current = requests.get("https://mmolb.com/api/seasons").json()["seasons"][0]["season_id"]
    yesno = ""

    # data folder initialization
    if not os.path.exists(os.path.join('data')):
        config.set_defaults()
        config.league_edit()
        print("Making data folder...")
        os.makedirs(os.path.join('data'))
    
    configuration = config.get_config()

    # roster info initialization
    if not os.path.isfile("data/roster_info.json"):
        print("No roster information detected, automatically fetching info...")
        update_rosters()
        update_rosters_deep()
    else:
        yesno = input("Update roster information? (enter 'y' for regular update, 'q' for quick update, and 'd' for deep update)\n")
        if yesno.lower() in ["y", "yes"]:
            update_rosters()
            yesno = input("Update individual player information? (enter 'y' for yes)")
        if yesno.lower() in ["q", "quick"]:
            update_rosters(quick=True)
        if yesno.lower() in ["d", "deep", "depth"]:
            update_rosters()
            update_rosters_deep()
            
    # games initialization
    if configuration["auto_game_update"] == "on" or not os.path.isfile("data/all_games.txt") or input("Update games? (takes a while) (enter 'yes' to activate) (do this on your first run)\n").lower() in ["y", "yes"]:
        update_games(current)
        with open("data/roster_info.json", "r") as f:
            roster_info = json.load(f)
            get_league_set = [i for i in roster_info["teams"].keys()]
            record_games(toi=get_league_set)

    get_pitch_zone_statistics()
    calculate_human_stats()
    calculate_percentiles()
    # quality_starts("quality_starts")
    # quality_starts("wins")
    search_program()

# TODO: migrate all_games.txt to a json file
# TODO: make a quick" roster update option"


# roster_info
#   players
#     id
#       name
#       position
#       team
#   teams
#     id
#       league
#       emoji
#       name
#       members
#   league
#     doesn't matter lol 