# season_odds.py
import json
import random as r
from tqdm import tqdm

def sim():
    with open("data/roster_info.json", "r", encoding="UTF-8") as f:
        roster_info = json.load(f)
        games_played = []
        current_standings = []
        for i in roster_info["teams"].keys():
            current_standings.append([roster_info["teams"][i]["emoji"] + " " + roster_info["teams"][i]["name"], roster_info["teams"][i]["wins"] - roster_info["teams"][i]["losses"], roster_info["teams"][i]["rd"]])
            games_played.append(roster_info["teams"][i]["wins"] + roster_info["teams"][i]["losses"])
        games_played = max(set(games_played), key=games_played.count)
        while games_played < 120:
            current_standings.sort(key = lambda x: x[1] + x[2] * 0.00001, reverse=True)
            games_played += 1
            # print(f"game day {games_played}")
            used = set()
            winners = []
            losers = []
            neither = [] # for the NPC team that hops in when there's an odd number
            if len(current_standings) % 2 == 1:
                for i in current_standings:
                    if "Cedar Point Coasters" in i[0]:
                        neither.append(i)
                        used.add(current_standings.index(i))
            for i in range(len(current_standings)):
                if i not in used:
                    scope = 10 if games_played % 4 != 0 else len(current_standings)
                    higher_opponent = current_standings[i]
                    lower_opponent = i + r.randrange(1, scope)
                    while lower_opponent >= len(current_standings) or lower_opponent in used:
                        lower_opponent = i + r.randrange(1, scope)
                    lower_opponent = current_standings[lower_opponent]
                    used.add(current_standings.index(higher_opponent))
                    used.add(current_standings.index(lower_opponent))
                    if r.random() < 0.5:
                        winners.append(higher_opponent)
                        losers.append(lower_opponent)
                    else:
                        losers.append(higher_opponent)
                        winners.append(lower_opponent)
                    # print(f"{current_standings.index(higher_opponent) + 1}. {higher_opponent[0]:<40} {current_standings.index(lower_opponent) + 1}. {lower_opponent[0]:<40}")
            for i in winners:
                i[1] += 1
            for i in losers:
                i[1] -= 1
            current_standings = (winners + losers + neither)
            # print("")
        current_standings.sort(key = lambda x: x[1] + x[2] * 0.00001, reverse=True)
        return current_standings
    
ranks = {}
count = 100000
for i in tqdm(range(count)):
    result = sim()
    for j in range(len(result)):
        if j + 1 not in ranks.keys():
            ranks[j + 1] = {}
        if result[j][0] not in ranks[j + 1].keys():
            ranks[j + 1][result[j][0]] = 0
        ranks[j + 1][result[j][0]] += 1
for i in ranks.keys():
    ranks[i] = {k: v for k, v in sorted(ranks[i].items(), key=lambda item: item[1], reverse=True)}
print("1ST PLACE")
for i in ranks[1].keys():
    print(i, f"{ranks[1][i] * 100 / count:.2f}%")
print("")
print("2ND PLACE")
for i in ranks[2].keys():
    print(i, f"{ranks[2][i] * 100 / count:.2f}%")