"""Structural smoke tests, built from documented (not captured) markup.
See fixtures_note.md — these prove the parsing logic is internally
consistent, not that it matches Golf Genius's real HTML byte-for-byte.
"""
from ggscrape.parsers.standings import parse_standings, parse_division_options, parse_team_rounds, parse_team_matchups
from ggscrape.parsers.roster import parse_roster
from ggscrape.parsers.player import parse_player
from ggscrape.parsers.teesheet import parse_tee_sheet, parse_round_panel_options, match_teams_to_opponents

STANDINGS_HTML = """
<table>
<tr><th>Number</th><th>Rank</th><th>Teams</th><th>Team Points</th>
    <th>Team Participation Points</th><th>Total Points</th><th>Team Members</th></tr>
<tr><td>1</td><td>1</td>
    <td><a href="/widgets/customized_team_standings/team_info?team=999&teamset=1">Fricke, Jeff + Fries, Ryan</a></td>
    <td>180.00</td><td>0.00</td><td>180.00</td><td>Fricke, Jeff | Fries, Ryan</td></tr>
<tr><td>2</td><td>2</td>
    <td><a href="/widgets/customized_team_standings/team_info?team=888&teamset=1">Haus, Greg + McWilliams, Matt</a></td>
    <td>176.00</td><td>0.00</td><td>176.00</td><td>Haus, Greg | McWilliams, Matt</td></tr>
<tr><td></td><td></td><td>Totals:</td><td>356.00</td><td>0.00</td><td>356.00</td><td></td></tr>
</table>
"""

ROSTER_HTML = """
<table>
<tr><th>Player</th><th>Eagles or better</th><th>Birdies</th><th>Pars</th>
    <th>Bogeys</th><th>Double Bogeys</th><th>Triple or worse</th></tr>
<tr><td><a href="/widgets/player_stats/member_info?member_id=12345">Holiday, Rusty</a></td>
    <td>0</td><td>3</td><td>18</td><td>36</td><td>20</td><td>13</td></tr>
<tr><td>Totals</td><td>0</td><td>3</td><td>18</td><td>36</td><td>20</td><td>13</td></tr>
</table>
"""

PLAYER_HTML = """
<h4>Rusty Holiday</h4>
<p>Low Net: <b>35.0</b></p>
<p>Low Gross: <b>43.0</b></p>
<p>Rounds Played: <b>11</b></p>
<p>Handicap Index: <b>16.9</b></p>

<table>
<tr><th>Date</th><th>Round</th><th>Eagles or better</th><th>Birdies</th><th>Pars</th>
    <th>Bogeys</th><th>Double Bogeys</th><th>Triple or worse</th></tr>
<tr><td>May 5, 2026</td><td>Round 2</td><td>0</td><td>0</td><td>1</td><td>4</td><td>2</td><td>2</td></tr>
<tr><td>May 12, 2026</td><td>Round 3</td><td>0</td><td>0</td><td>4</td><td>2</td><td>2</td><td>1</td></tr>
</table>

<!-- Real Golf Genius scorecard pages stack a Back-9 block and a Front-9
     block in the SAME <table>, each with its own 'Hole' header row and its
     own repeat of Course Par / League Average / Player Average / per-date
     rows. This fixture mirrors that (see tests/fixtures_note.md) to catch
     the bug where the second block's rows overwrote the first's. -->
<table>
<tr><td>[+]Miracle Hill (Blue - Men - Back 9)</td></tr>
<tr><td>Hole</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td>
    <td>10</td><td>11</td><td>12</td><td>13</td><td>14</td><td>15</td><td>16</td><td>17</td><td>18</td></tr>
<tr><td>Course Par</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
    <td>4</td><td>3</td><td>4</td><td>5</td><td>4</td><td>3</td><td>4</td><td>4</td><td>4</td></tr>
<tr><td>League Average</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
    <td>4.9</td><td>4.1</td><td>4.9</td><td>5.9</td><td>5.0</td><td>4.0</td><td>5.4</td><td>5.2</td><td>5.0</td></tr>
<tr><td>Player Average</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
    <td>5.8</td><td>6.0</td><td>5.0</td><td>5.6</td><td>4.6</td><td>4.4</td><td>5.2</td><td>4.6</td><td>5.8</td></tr>
<tr><td>May 5, 2026</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
    <td>7</td><td>3</td><td>5</td><td>6</td><td>6</td><td>4</td><td>6</td><td>5</td><td>7</td></tr>
<tr><td>[+]Miracle Hill (Blue - Men - Front 9)</td></tr>
<tr><td>Hole</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td>
    <td>10</td><td>11</td><td>12</td><td>13</td><td>14</td><td>15</td><td>16</td><td>17</td><td>18</td></tr>
<tr><td>Course Par</td>
    <td>4</td><td>3</td><td>5</td><td>4</td><td>4</td><td>3</td><td>4</td><td>5</td><td>3</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>League Average</td>
    <td>5.4</td><td>3.9</td><td>6.0</td><td>5.1</td><td>5.1</td><td>4.0</td><td>5.0</td><td>5.9</td><td>4.0</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>Player Average</td>
    <td>5.5</td><td>3.8</td><td>6.5</td><td>5.7</td><td>6.3</td><td>4.2</td><td>4.8</td><td>6.0</td><td>4.0</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>May 12, 2026</td>
    <td>5</td><td>4</td><td>7</td><td>6</td><td>9</td><td>3</td><td>4</td><td>5</td><td>3</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
"""


DIVISION_FORM_HTML = """
<form action="https://mhgc-tuesdaynightleague.golfgenius.com/leagues/1/widgets/team_standings">
<select name="teamset" id="teamset">
<option value="">All Divisions/Teams</option>
<option value="12541441646752988742">All Golfers/Teams</option>
<option value="12579376722559926027" selected="selected">Callaway Division/Teams</option>
<option value="12579377853042294540">Titleist Division/Teams</option>
</select>
<select name="sequence" id="sequence">
<option value="12541420283719876603">All Rounds</option>
<option value="12579391288941510322" selected="selected">Tue, May  5 - Tue, Aug 11</option>
</select>
</form>
"""


TEAM_INFO_HTML = """
<table>
<thead><tr><th></th><th>Round Date</th><th>Round Name</th><th>Points</th></tr></thead>
<tbody>
<tr><td>[+]</td><td>May 05, 2026</td><td>Round 2</td><td>18.00</td></tr>
<tr><td>
<table>
<tr><td>Points</td><td>Phillips, Nick  +  Holiday, Rusty</td><td></td><td>Long, Mitchell  +  Pick, Connor</td><td>Points</td></tr>
<tr><td>5.50</td><td>Holiday, Rusty</td><td>vs.</td><td>Long, Mitchell</td><td>3.50</td></tr>
<tr><td>6.50</td><td>Phillips, Nick</td><td>vs.</td><td>Pick, Connor</td><td>2.50</td></tr>
<tr><td>12.00</td><td></td><td>Totals</td><td></td><td>6.00</td></tr>
<tr><td>Phillips, Nick  +  Holiday, Rusty vs Long, Mitchell  +  Pick, Connor</td><td>6.00</td></tr>
<tr><td>6.00</td><td></td><td>Totals</td><td></td><td>3.00</td></tr>
</table>
</td></tr>
<tr><td>[+]</td><td>Jun 16, 2026</td><td>Round 8</td><td>8.50</td></tr>
<tr><td>
<table>
<tr><td>Points</td><td>Phillips, Nick  +  Stoakes, Gabe</td><td></td><td>Fricke, Jeff  +  Fries, Ryan</td><td>Points</td></tr>
<tr><td>4.50</td><td>Phillips, Nick</td><td>vs.</td><td>Fries, Ryan</td><td>4.50</td></tr>
<tr><td>2.00</td><td>Stoakes, Gabe</td><td>vs.</td><td>Fricke, Jeff</td><td>7.00</td></tr>
<tr><td>6.50</td><td></td><td>Totals</td><td></td><td>11.50</td></tr>
<tr><td>Fricke, Jeff  +  Fries, Ryan vs Phillips, Nick  +  Stoakes, Gabe</td><td>2.00</td></tr>
<tr><td>2.00</td><td></td><td>Totals</td><td></td><td>7.00</td></tr>
</table>
</td></tr>
<tr><td>[+]</td><td>Jul 28, 2026</td><td>Round 14</td><td>15.50</td></tr>
<tr><td>
<table>
<!-- Real site behavior: some rounds put the team-total block FIRST,
     reversed from every other round above. A position-based parser
     (assuming row 0 is always the header) silently drops these. -->
<tr><td>Phillips, Nick  +  Holiday, Rusty vs Smith, Nick  +  Hand, Hunter</td><td>5.00</td></tr>
<tr><td>5.00</td><td></td><td>Totals</td><td></td><td>4.00</td></tr>
<tr><td>Points</td><td>Phillips, Nick  +  Holiday, Rusty</td><td></td><td>Smith, Nick  +  Hand, Hunter</td><td>Points</td></tr>
<tr><td>6.00</td><td>Phillips, Nick</td><td>vs.</td><td>Hand, Hunter</td><td>3.00</td></tr>
<tr><td>4.50</td><td>Holiday, Rusty</td><td>vs.</td><td>Smith, Nick</td><td>4.50</td></tr>
<tr><td>10.50</td><td></td><td>Totals</td><td></td><td>7.50</td></tr>
</table>
</td></tr>
</tbody>
</table>
"""


def test_parse_team_rounds():
    rounds = parse_team_rounds(TEAM_INFO_HTML)
    assert [(r.round_num, r.points) for r in rounds] == [(2, 18.0), (8, 8.5), (14, 15.5)]


def test_parse_team_matchups():
    matchups = parse_team_matchups(TEAM_INFO_HTML)
    assert len(matchups) == 3
    r2, r8, r14 = matchups
    assert r2.opponent == "Long, Mitchell + Pick, Connor"
    assert r2.us == 18.0 and r2.them == 9.0
    assert len(r2.pairings) == 2
    assert r2.pairings[0].player == "Holiday, Rusty"
    assert r2.pairings[0].opponent == "Long, Mitchell"
    assert r2.pairings[0].us == 5.5 and r2.pairings[0].them == 3.5
    assert r2.pairings[1].player == "Phillips, Nick"
    # Round 8: Rusty was subbed out for Stoakes — pairings show whoever
    # actually played, no single "watched" player assumed.
    assert r8.opponent == "Fricke, Jeff + Fries, Ryan"
    assert {p.player for p in r8.pairings} == {"Phillips, Nick", "Stoakes, Gabe"}
    # Round 14: team-total block appears BEFORE the header/pairings block
    # (reversed row order) — must still be found correctly, not skipped.
    assert r14.opponent == "Smith, Nick + Hand, Hunter"
    assert r14.us == 15.5 and r14.them == 11.5
    assert len(r14.pairings) == 2
    assert {p.player for p in r14.pairings} == {"Phillips, Nick", "Holiday, Rusty"}


def test_parse_division_options():
    opts = parse_division_options(DIVISION_FORM_HTML)
    assert opts.teamsets["Callaway Division/Teams"] == "12579376722559926027"
    assert opts.teamsets["Titleist Division/Teams"] == "12579377853042294540"
    assert opts.default_sequence == "12579391288941510322"
    assert opts.teamset_id("titleist") == "12579377853042294540"


def test_standings():
    teams = parse_standings(STANDINGS_HTML)
    assert len(teams) == 2
    assert teams[0].name == "Fricke, Jeff + Fries, Ryan"
    assert teams[0].team_points == 180.0
    assert teams[0].team_id == "999"
    assert teams[0].members == ["Fricke, Jeff", "Fries, Ryan"]


def test_roster():
    players = parse_roster(ROSTER_HTML)
    assert len(players) == 1
    assert players[0].name == "Holiday, Rusty"
    assert players[0].member_id == "12345"
    assert players[0].bogeys == 36


def test_player():
    p = parse_player(PLAYER_HTML)
    assert p.hcp_index == 16.9
    assert p.low_gross == 43.0
    assert len(p.scoring) == 2
    assert p.scoring[0].round_num == 2

    # Back-9 and Front-9 blocks share one <table> — both must survive intact,
    # not have the second block's rows clobber the first's.
    assert "back" in p.course and "front" in p.course
    assert p.course["back"].par == [4, 3, 4, 5, 4, 3, 4, 4, 4]
    assert p.course["front"].par == [4, 3, 5, 4, 4, 3, 4, 5, 3]

    assert len(p.hole_rounds) == 2
    by_round = {h.round_num: h for h in p.hole_rounds}
    assert by_round[2].nine == "Back"
    assert sum(by_round[2].holes) == 49
    assert by_round[3].nine == "Front"
    assert sum(by_round[3].holes) == 46


TEE_SHEET_HTML = """
<select name="widget_round_panel_selector">
<option value="/widgets/next_round?round_id=111">Round 15 (Tue, August  4)</option>
<option selected="selected" value="/widgets/next_round?round_id=222">Round 16 (Tue, August 11)</option>
</select>
<table>
<tr class='search_rows hidden-xs'>
<td> 5:30 PM</td><td>11A</td>
<td>
<div class='players_portrait'>Kellner, Allison  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Schoneman, Greta  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Holiday, Rusty  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Phillips, Nick  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
</td>
<td> 5:30 PM</td><td>12</td>
<td>
<div class='players_portrait'>Rupe, Nick  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Frost, Jerod  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Deas, Ben  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Lindell Jr., Ted  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
</td>
</tr>
<tr class='search_rows visible-xs hidden-sm hidden-md hidden-lg'>
<td> 5:30 PM</td><td>11A</td>
<td>
<div class='players_portrait'>Kellner, Allison  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Schoneman, Greta  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Holiday, Rusty  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
<div class='players_portrait'>Phillips, Nick  <span class='tee_abbr'></span><div class='division_and_flight'></div></div>
<div class='clearfix'></div>
</td>
</tr>
</table>
"""


def test_parse_round_panel_options():
    opts = parse_round_panel_options(TEE_SHEET_HTML)
    assert [(o.round_num, o.date, o.round_id) for o in opts] == [
        (15, "Tue, August 4", "111"),
        (16, "Tue, August 11", "222"),
    ]
    assert opts[0].selected is False and opts[1].selected is True


def test_parse_tee_sheet():
    matches = parse_tee_sheet(TEE_SHEET_HTML)
    # the visible-xs duplicate row must not double-count hole 11A
    assert len(matches) == 2
    by_hole = {m.hole: m for m in matches}
    assert by_hole["11A"].team_a == ["Kellner, Allison", "Schoneman, Greta"]
    assert by_hole["11A"].team_b == ["Holiday, Rusty", "Phillips, Nick"]
    assert by_hole["12"].team_a == ["Rupe, Nick", "Frost, Jerod"]
    assert by_hole["12"].team_b == ["Deas, Ben", "Lindell Jr., Ted"]


def test_match_teams_to_opponents():
    matches = parse_tee_sheet(TEE_SHEET_HTML)
    team_members = {
        "Kellner, Allison + Schoneman, Greta": ["Kellner, Allison", "Schoneman, Greta"],
        "Phillips, Nick + Holiday, Rusty": ["Holiday, Rusty", "Phillips, Nick"],
        "Frost, Jerod + Rupe, Nick": ["Rupe, Nick", "Frost, Jerod"],
        "Deas, Ben + Lindell Jr., Ted": ["Deas, Ben", "Lindell Jr., Ted"],
    }
    opp = match_teams_to_opponents(matches, team_members)
    assert opp["Phillips, Nick + Holiday, Rusty"] == "Kellner, Allison + Schoneman, Greta"
    assert opp["Frost, Jerod + Rupe, Nick"] == "Deas, Ben + Lindell Jr., Ted"


if __name__ == "__main__":
    test_standings()
    test_parse_division_options()
    test_parse_team_rounds()
    test_parse_team_matchups()
    test_roster()
    test_player()
    test_parse_round_panel_options()
    test_parse_tee_sheet()
    test_match_teams_to_opponents()
    print("ALL STRUCTURAL SMOKE TESTS PASSED")
