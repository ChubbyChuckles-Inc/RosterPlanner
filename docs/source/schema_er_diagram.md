# SQLite Schema ER Diagram

Generated Mermaid ER diagram for current schema (Milestone 3.1.1):

```mermaid
erDiagram
  availability {
    INTEGER availability_id
    INTEGER player_id
    TEXT date
    TEXT status
    INTEGER confidence?
    TEXT note?
    TEXT created_at?
  }

  club {
    INTEGER club_id
    TEXT name
    TEXT short_name?
    TEXT created_at?
  }

  division {
    INTEGER division_id
    TEXT name
    TEXT level?
    TEXT category?
    INTEGER season
    TEXT created_at?
  }

  match {
    INTEGER match_id
    INTEGER division_id
    INTEGER home_team_id
    INTEGER away_team_id
    TEXT match_date
    INTEGER round?
    INTEGER home_score?
    INTEGER away_score?
    TEXT status?
    TEXT created_at?
  }

  planning_scenario {
    INTEGER scenario_id
    TEXT name
    INTEGER division_id?
    TEXT match_date?
    TEXT notes?
    TEXT created_at?
  }

  player {
    INTEGER player_id
    INTEGER team_id?
    TEXT full_name
    INTEGER live_pz?
    INTEGER position?
    TEXT created_at?
  }

  scenario_player {
    INTEGER scenario_id
    INTEGER player_id
    INTEGER slot?
    TEXT role?
  }

  team {
    INTEGER team_id
    INTEGER club_id
    INTEGER division_id
    TEXT name
    TEXT code?
    TEXT created_at?
  }

  availability }o--|| player : "player_id -> player_id"
  match }o--|| team : "away_team_id -> team_id"
  match }o--|| team : "home_team_id -> team_id"
  match }o--|| division : "division_id -> division_id"
  planning_scenario }o--|| division : "division_id -> division_id"
  player }o--|| team : "team_id -> team_id"
  scenario_player }o--|| player : "player_id -> player_id"
  scenario_player }o--|| planning_scenario : "scenario_id -> scenario_id"
  team }o--|| division : "division_id -> division_id"
  team }o--|| club : "club_id -> club_id"
```
