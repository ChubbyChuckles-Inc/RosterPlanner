#!/usr/bin/env python3
"""
Script to fetch the source code of a website and save it to the experiment directory.
Compatible with Python 3.13.7
"""

import urllib.request
import urllib.error
import os
import re
from datetime import datetime


def fetch_website_source(url: str, output_filename: str = None) -> str:
    """
    Fetch the source code of a website and save it to the experiment directory.

    Args:
        url: The URL to fetch
        output_filename: Optional filename for the output. If not provided,
                        will use a timestamp-based filename.

    Returns:
        The path to the saved file

    Raises:
        urllib.error.URLError: If the URL cannot be accessed
        urllib.error.HTTPError: If the server returns an error
    """
    try:
        print(f"Fetching content from: {url}")

        # Create request with headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')

        print(f"Successfully fetched {len(content)} characters")

        # Generate filename if not provided
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"website_source_{timestamp}.html"

        # Ensure experiment directory exists
        experiment_dir = "experiment"
        os.makedirs(experiment_dir, exist_ok=True)

        # Full path for output file
        output_path = os.path.join(experiment_dir, output_filename)

        # Save content to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Content saved to: {output_path}")
        return output_path

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        raise
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


def extract_team_links(html_content: str) -> tuple[list[str], list[str], list[str]]:
    """
    Extract team roster links from the HTML content and generate match plan links for both halves.

    Args:
        html_content: The HTML content to parse

    Returns:
        A tuple containing (team_roster_links, first_half_match_plan_links, second_half_match_plan_links)
    """
    # Extract team roster links (with L3=Mannschaften&L3P= parameter)
    team_roster_pattern = r'href="([^"]*L3=Mannschaften[^"]*)"'
    team_roster_links = re.findall(team_roster_pattern, html_content)

    # Clean up the links by removing duplicates
    team_roster_links = list(set(team_roster_links))

    # Generate ranking table links from team roster links
    ranking_table_links = []
    root_url = "https://leipzig.tischtennislive.de/"

    for roster_link in team_roster_links:
        # Extract the division part (everything up to L3=)
        division_part = re.match(r'(\?[^&]*&L2=TTStaffeln&L2P=[^&]*)', roster_link)
        if division_part:
            division_url = division_part.group(1)
            # Build the ranking table link
            ranking_link = f"{root_url}{division_url}&L3=Tabelle"

            ranking_table_links.append(ranking_link)

    return team_roster_links, ranking_table_links


def fetch_team_roster_sources(team_roster_links: list[str], experiment_dir: str = "experiment") -> list[str]:
    """
    Fetch the source code of each team roster page and save to experiment directory.

    Args:
        team_roster_links: List of team roster URLs to fetch
        experiment_dir: Directory to save the files

    Returns:
        List of file paths where team roster sources were saved
    """
    saved_files = []
    root_url = "https://leipzig.tischtennislive.de/"

    for i, roster_link in enumerate(team_roster_links, 1):
        try:
            # Add root URL if not present
            if not roster_link.startswith('http'):
                full_url = f"{root_url}{roster_link}"
            else:
                full_url = roster_link

            print(f"Fetching team roster {i}/{len(team_roster_links)}: {full_url}")

            # Create request with headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8')

            # Generate filename based on team identifier
            team_id = re.search(r'L2P=([^&]*)', roster_link)
            if team_id:
                filename = f"team_roster_L2P_{team_id.group(1)}.html"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"team_roster_{i}_{timestamp}.html"

            # Ensure experiment directory exists
            os.makedirs(experiment_dir, exist_ok=True)

            # Full path for output file
            output_path = os.path.join(experiment_dir, filename)

            # Save content to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            saved_files.append(output_path)
            print(f"  Saved to: {output_path}")

        except urllib.error.HTTPError as e:
            print(f"  HTTP Error {e.code}: {e.reason} for {full_url}")
        except urllib.error.URLError as e:
            print(f"  URL Error: {e.reason} for {full_url}")
        except Exception as e:
            print(f"  Unexpected error: {e} for {full_url}")

    return saved_files


def extract_team_names_and_divisions(html_content: str) -> dict:
    """
    Extract team names and divisions from the HTML table.

    Args:
        html_content: The HTML content containing the team overview table

    Returns:
        Dictionary mapping team IDs (L2P values) to (team_name, division_name) tuples
    """
    teams_info = {}

    # Find all team rows in the table - improved regex to handle the HTML structure better
    # Look for the pattern: <tr class="..."><td>...</td><td>TEAM_NAME</td><td>DIVISION_NAME</td><td><a href="...L2P=TEAM_ID...">...</td>
    team_rows = re.findall(r'<tr class="(?:ContentText|CONTENTTABLETEXT2ndLine)">[^<]*<td[^>]*>[^<]*</td>[^<]*<td[^>]*>([^<]+)</td>[^<]*<td[^>]*>([^<]+)</td>[^<]*<td[^>]*>[^<]*<a href="[^"]*L2P=([^&"]+)', html_content, re.DOTALL | re.IGNORECASE)

    for team_name, division_name, team_id in team_rows:
        clean_team_name = team_name.strip()
        clean_division_name = division_name.strip()
        if clean_team_name and clean_division_name and team_id:
            teams_info[team_id] = (clean_team_name, clean_division_name)

    # If no teams found with the first pattern, try a more flexible approach
    if not teams_info:
        # Alternative pattern that looks for the team name and division in the table structure
        alt_pattern = r'<tr class="(?:ContentText|CONTENTTABLETEXT2ndLine)">[^<]*<td[^>]*>[^<]*</td>[^<]*<td[^>]*>([^<]+)</td>[^<]*<td[^>]*>([^<]+)</td>[^<]*<td[^>]*>[^<]*<a href="[^"]*L2P=([^&"]+)[^"]*"[^>]*>[^<]*</a>[^<]*</td>'
        alt_team_rows = re.findall(alt_pattern, html_content, re.DOTALL | re.IGNORECASE)

        for team_name, division_name, team_id in alt_team_rows:
            clean_team_name = team_name.strip()
            clean_division_name = division_name.strip()
            if clean_team_name and clean_division_name and team_id:
                teams_info[team_id] = (clean_team_name, clean_division_name)

    return teams_info


def fetch_ranking_table_sources(ranking_table_links: list[str], teams_info: dict, experiment_dir: str = "experiment") -> list[str]:
    """
    Fetch the source code of each ranking table page and save to experiment directory.

    Args:
        ranking_table_links: List of ranking table URLs to fetch
        teams_info: Dictionary mapping team IDs to (team_name, division_name) tuples
        experiment_dir: Directory to save the files

    Returns:
        List of file paths where ranking table sources were saved
    """
    saved_files = []
    root_url = "https://leipzig.tischtennislive.de/"

    for i, ranking_link in enumerate(ranking_table_links, 1):
        try:
            # Add root URL if not present
            if not ranking_link.startswith('http'):
                full_url = f"{root_url}{ranking_link}"
            else:
                full_url = ranking_link

            print(f"Fetching ranking table {i}/{len(ranking_table_links)}: {full_url}")

            # Create request with headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8')

            # Generate filename based on division name
            # Extract L2P (division ID) from the URL
            division_id = re.search(r'L2P=([^&]+)', ranking_link)
            if division_id:
                div_id = division_id.group(1)
                # Get division name from teams_info
                if div_id in teams_info:
                    team_name, division_name = teams_info[div_id]
                    # Clean division name for filename (remove special characters)
                    clean_division_name = re.sub(r'[^\w\s-]', '', division_name).strip()
                    clean_division_name = re.sub(r'[-\s]+', '_', clean_division_name)
                    filename = f"ranking_table_{clean_division_name}.html"
                else:
                    filename = f"ranking_table_division_{div_id}.html"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"ranking_table_{i}_{timestamp}.html"

            # Ensure experiment directory exists
            os.makedirs(experiment_dir, exist_ok=True)

            # Full path for output file
            output_path = os.path.join(experiment_dir, filename)

            # Save content to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            saved_files.append(output_path)
            print(f"  Saved to: {output_path}")

        except urllib.error.HTTPError as e:
            print(f"  HTTP Error {e.code}: {e.reason} for {full_url}")
        except urllib.error.URLError as e:
            print(f"  URL Error: {e.reason} for {full_url}")
        except Exception as e:
            print(f"  Unexpected error: {e} for {full_url}")

    return saved_files


def extract_ranking_data_from_pages(experiment_dir: str = "experiment", teams_info: dict = None) -> dict:
    """
    Extract team names and roster links from all ranking table HTML files.

    Args:
        experiment_dir: Directory containing the ranking table HTML files
        teams_info: Dictionary mapping team IDs to (team_name, division_name) tuples

    Returns:
        Dictionary with division information and team roster links
    """
    import glob

    # Find all ranking table files
    ranking_files = glob.glob(os.path.join(experiment_dir, "ranking_table_*.html"))

    all_ranking_data = {}

    for ranking_file in ranking_files:
        try:
            # Extract division name from filename
            filename = os.path.basename(ranking_file)
            # Remove the .html extension and ranking_table_ prefix
            division_name = filename.replace('ranking_table_', '').replace('.html', '')
            # Clean up the division name
            division_name = re.sub(r'_+', ' ', division_name).strip()

            # Read the HTML content
            with open(ranking_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract team data from the "Mannschaften" section
            teams = []

            # Look for the Mannschaften section and extract team names and links
            # Pattern to find the Mannschaften ul/li structure
            mannschaften_pattern = r'<li[^>]*>.*?href="[^"]*"[^>]*>Mannschaften</a>.*?<ul[^>]*>(.*?)</ul>'
            mannschaften_match = re.search(mannschaften_pattern, content, re.DOTALL | re.IGNORECASE)

            if mannschaften_match:
                mannschaften_content = mannschaften_match.group(1)

                # Extract individual team entries
                team_pattern = r'<li[^>]*>.*?href="([^"]*)"[^>]*>.*?span[^>]*>([^<]+)</span>'
                team_matches = re.findall(team_pattern, mannschaften_content, re.DOTALL | re.IGNORECASE)

                for roster_link, team_name in team_matches:
                    clean_team_name = team_name.strip()

                    if clean_team_name and roster_link:
                        teams.append({
                            'team_name': clean_team_name,
                            'roster_link': roster_link
                        })

            if teams:
                # Get division ID from teams_info if available
                division_id = None
                for team_id, (team_name, div_name) in teams_info.items():
                    if div_name == division_name:
                        division_id = team_id
                        break

                all_ranking_data[division_name] = {
                    'division_id': division_id,
                    'teams': teams,
                    'total_teams': len(teams)
                }
                print(f"  Extracted {len(teams)} teams from {division_name}")

        except Exception as e:
            print(f"  Error processing {ranking_file}: {e}")

    return all_ranking_data


def fetch_all_team_rosters(ranking_data: dict, experiment_dir: str = "experiment") -> dict:
    """
    Fetch all team rosters from all divisions based on ranking data.

    Args:
        ranking_data: Dictionary with division information and team roster links
        experiment_dir: Directory to save the team roster files

    Returns:
        Dictionary with all team roster information
    """
    root_url = "https://leipzig.tischtennislive.de/"
    all_team_rosters = {}

    total_teams = 0
    for division_name, division_info in ranking_data.items():
        teams = division_info['teams']
        total_teams += len(teams)

    print(f"  Preparing to fetch {total_teams} team rosters from {len(ranking_data)} divisions...")

    for division_name, division_info in ranking_data.items():
        teams = division_info['teams']

        for i, team in enumerate(teams, 1):
            try:
                roster_link = team['roster_link']

                # Add root URL if not present
                if not roster_link.startswith('http'):
                    full_url = f"{root_url}{roster_link}"
                else:
                    full_url = roster_link

                print(f"  Fetching team roster {i}/{len(teams)} in {division_name}: {team['team_name']}")

                # Create request with headers to mimic a browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                req = urllib.request.Request(full_url, headers=headers)
                with urllib.request.urlopen(req) as response:
                    content = response.read().decode('utf-8')

                # Generate filename based on team name and division
                clean_team_name = re.sub(r'[^\w\s-]', '', team['team_name']).strip()
                clean_team_name = re.sub(r'[-\s]+', '_', clean_team_name)
                clean_division_name = re.sub(r'[^\w\s-]', '', division_name).strip()
                clean_division_name = re.sub(r'[-\s]+', '_', clean_division_name)

                # Extract team ID from roster link for unique identification
                team_id_match = re.search(r'L3P=(\d+)', roster_link)
                if team_id_match:
                    team_id = team_id_match.group(1)
                    filename = f"team_roster_{clean_division_name}_{clean_team_name}_{team_id}.html"
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"team_roster_{clean_division_name}_{clean_team_name}_{timestamp}.html"

                # Ensure experiment directory exists
                os.makedirs(experiment_dir, exist_ok=True)

                # Full path for output file
                output_path = os.path.join(experiment_dir, filename)

                # Save content to file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Store team information
                if division_name not in all_team_rosters:
                    all_team_rosters[division_name] = []

                all_team_rosters[division_name].append({
                    'team_name': team['team_name'],
                    'team_id': team_id if team_id_match else None,
                    'roster_link': roster_link,
                    'file_path': output_path
                })

                print(f"    Saved to: {output_path}")

            except urllib.error.HTTPError as e:
                print(f"    HTTP Error {e.code}: {e.reason} for {full_url}")
            except urllib.error.URLError as e:
                print(f"    URL Error: {e.reason} for {full_url}")
            except Exception as e:
                print(f"    Unexpected error: {e} for {full_url}")

    return all_team_rosters


def extract_match_data_from_rosters(experiment_dir: str = "experiment") -> dict:
    """
    Extract match data from all team roster HTML files.

    Args:
        experiment_dir: Directory containing the team roster HTML files

    Returns:
        Dictionary with team IDs as keys and list of match dictionaries as values
    """
    import glob

    # Find all team roster files
    roster_files = glob.glob(os.path.join(experiment_dir, "team_roster_*.html"))

    all_matches_data = {}

    for roster_file in roster_files:
        try:
            # Extract team ID from filename
            team_id = re.search(r'team_roster_L2P_(\d+)\.html', os.path.basename(roster_file))
            if not team_id:
                continue

            team_id = team_id.group(1)

            # Read the HTML content
            with open(roster_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract match data from the match table
            matches = []

            # Pattern to find match rows - both completed and upcoming matches
            # Look for <tr ID="Spiel..." patterns
            match_rows = re.findall(r'<tr[^>]*ID="Spiel\d+"[^>]*>.*?</tr>', content, re.DOTALL | re.IGNORECASE)

            for match_row in match_rows:
                match_info = {}

                # Extract match number
                match_number_match = re.search(r'ID="Spiel(\d+)"', match_row)
                if match_number_match:
                    match_info['match_number'] = match_number_match.group(1)

                # Extract match details using a more targeted approach
                # The structure is: <td>Match Number</td><td>Weekday</td><td>Date</td><td>Time</td><td>Home Team</td><td>Guest Team</td><td>Score/Status</td>

                # Extract all td content in order
                td_contents = re.findall(r'<td[^>]*>(.*?)</td>', match_row, re.DOTALL | re.IGNORECASE)

                if len(td_contents) >= 8:
                    # Clean up the td contents
                    clean_contents = []
                    for td_content in td_contents:
                        # Remove HTML tags and extra whitespace
                        clean_content = re.sub(r'<[^>]+>', '', td_content)
                        clean_content = re.sub(r'&nbsp;', '', clean_content)
                        clean_content = clean_content.strip()
                        clean_contents.append(clean_content)

                    # Extract match details based on position
                    if len(clean_contents) >= 8:
                        match_info['match_number'] = clean_contents[1] if len(clean_contents) > 1 else ''
                        match_info['weekday'] = clean_contents[3] if len(clean_contents) > 3 else ''
                        match_info['date'] = clean_contents[4] if len(clean_contents) > 4 else ''
                        match_info['time'] = clean_contents[6] if len(clean_contents) > 6 else ''
                        match_info['home_team'] = clean_contents[7] if len(clean_contents) > 7 else ''
                        match_info['guest_team'] = clean_contents[8] if len(clean_contents) > 8 else ''

                        # Check if it's a completed match (has score) or upcoming match
                        if len(clean_contents) > 9 and clean_contents[9]:
                            # Look for score in the format "X:Y"
                            score_match = re.search(r'(\d+):(\d+)', clean_contents[9])
                            if score_match:
                                match_info['home_score'] = score_match.group(1)
                                match_info['guest_score'] = score_match.group(2)
                                match_info['status'] = 'completed'
                            else:
                                match_info['status'] = 'completed'
                                match_info['home_score'] = ''
                                match_info['guest_score'] = ''
                        else:
                            match_info['status'] = 'upcoming'
                            match_info['home_score'] = ''
                            match_info['guest_score'] = ''

                if match_info:
                    matches.append(match_info)

            if matches:
                all_matches_data[team_id] = matches
                print(f"  Extracted {len(matches)} matches from team {team_id}")

        except Exception as e:
            print(f"  Error processing {roster_file}: {e}")

    return all_matches_data


def extract_player_data_from_rosters(experiment_dir: str = "experiment") -> dict:
    """
    Extract player names and LivePZ values from all team roster HTML files.

    Args:
        experiment_dir: Directory containing the team roster HTML files

    Returns:
        Dictionary with team IDs as keys and list of (player_name, live_pz) tuples as values
    """
    import glob

    # Find all team roster files
    roster_files = glob.glob(os.path.join(experiment_dir, "team_roster_L2P_*.html"))

    all_players_data = {}

    for roster_file in roster_files:
        try:
            # Extract team ID from filename
            team_id = re.search(r'team_roster_L2P_(\d+)\.html', os.path.basename(roster_file))
            if not team_id:
                continue

            team_id = team_id.group(1)

            # Read the HTML content
            with open(roster_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract player data using a more targeted approach
            # Based on the HTML structure provided by the user, we need to find:
            # 1. Player names in links with href containing "Spieler"
            # 2. LivePZ values in cells with class="tooltip" and title containing "LivePZ-Wert"

            # Find all player links - including those with empty LivePZ cells
            player_links = re.findall(r'<a[^>]*href="[^"]*Spieler[^"]*"[^>]*>([^<]+)</a>', content, re.IGNORECASE)

            # Also try to find players by looking for the row structure
            # This will help capture players that might be missed by the first pattern
            additional_players = re.findall(r'<tr[^>]*>.*?Spieler[^>]*>.*?href="[^"]*Spieler[^"]*"[^>]*>([^<]+)</a>', content, re.DOTALL | re.IGNORECASE)

            # Combine and deduplicate
            all_player_links = list(set(player_links + additional_players))

            # Find all LivePZ cells - handle cases with additional text in title and HTML content
            live_pz_cells = re.findall(r'<td[^>]*class="tooltip"[^>]*title="LivePZ-Wert[^"]*"[^>]*>.*?</td>', content, re.IGNORECASE | re.DOTALL)

            # Clean up the extracted data
            clean_player_links = [name.strip() for name in all_player_links if name.strip()]

            # Clean LivePZ values - handle HTML content and extract just the number
            clean_live_pz = []
            for cell in live_pz_cells:
                # Extract content between the opening and closing tags
                cell_content = re.sub(r'<td[^>]*class="tooltip"[^>]*title="LivePZ-Wert[^"]*"[^>]*>(.*?)</td>', r'\1', cell, flags=re.IGNORECASE | re.DOTALL)

                if cell_content.strip():
                    # Remove HTML tags and extract the number
                    clean_pz = re.sub(r'<[^>]+>', '', cell_content)  # Remove HTML tags
                    clean_pz = re.sub(r'&nbsp;', '', clean_pz)  # Remove &nbsp;
                    clean_pz = re.sub(r'\s+', '', clean_pz)  # Remove extra whitespace
                    # Extract the last number found (in case there are multiple)
                    numbers = re.findall(r'\d+', clean_pz)
                    if numbers:
                        clean_live_pz.append(numbers[-1])  # Take the last number found
                    else:
                        clean_live_pz.append('')  # Empty if no number found
                else:
                    clean_live_pz.append('')  # Empty cell

            # Create a comprehensive approach to extract all players and their LivePZ values
            players = []

            # First, find ALL player names by looking for Spieler links
            all_player_names = []
            player_name_pattern = r'href="[^"]*Spieler[^"]*"[^>]*>([^<]+)</a>'
            all_player_matches = re.findall(player_name_pattern, content, re.IGNORECASE)

            for match in all_player_matches:
                clean_name = match.strip()
                if clean_name and clean_name not in all_player_names:
                    all_player_names.append(clean_name)

            # Now try to find LivePZ values for each player
            for player_name in all_player_names:
                # Look for this specific player's row
                player_row_pattern = f'href="[^"]*Spieler[^"]*"[^>]*>{re.escape(player_name)}</a>.*?<td[^>]*class="tooltip"[^>]*title="LivePZ-Wert[^"]*"[^>]*>(.*?)</td>'
                player_row_match = re.search(player_row_pattern, content, re.DOTALL | re.IGNORECASE)

                if player_row_match:
                    live_pz_content = player_row_match.group(1)
                    if live_pz_content.strip():
                        # Clean the LivePZ content
                        clean_pz = re.sub(r'<[^>]+>', '', live_pz_content)  # Remove HTML tags
                        clean_pz = re.sub(r'&nbsp;', '', clean_pz)  # Remove &nbsp;
                        clean_pz = re.sub(r'\s+', '', clean_pz)  # Remove extra whitespace
                        numbers = re.findall(r'\d+', clean_pz)
                        if numbers:
                            players.append((player_name, numbers[-1]))
                        else:
                            players.append((player_name, ''))
                    else:
                        # Empty LivePZ cell
                        players.append((player_name, ''))
                else:
                    # Player found but no LivePZ cell found - still include them
                    players.append((player_name, ''))

            # If no players found with this approach, fall back to the original method
            if not players:
                # Fallback: try to match by position
                for i, player_name in enumerate(clean_player_links):
                    if i < len(clean_live_pz):
                        players.append((player_name, clean_live_pz[i]))
                    else:
                        players.append((player_name, ''))

            # Clean up the extracted data
            players_data = []
            for player_name, live_pz in players:
                # Clean player name (remove extra whitespace)
                clean_name = re.sub(r'\s+', ' ', player_name.strip())
                # Clean LivePZ value (remove extra whitespace and &nbsp;)
                clean_pz = re.sub(r'\s+', '', live_pz.strip().replace('&nbsp;', ''))

                if clean_name and clean_pz:
                    players_data.append((clean_name, clean_pz))

            if players_data:
                all_players_data[team_id] = players_data
                print(f"  Extracted {len(players_data)} players from team {team_id}")

        except Exception as e:
            print(f"  Error processing {roster_file}: {e}")

    return all_players_data


def main():
    """Main function to run the script."""
    url = "https://leipzig.tischtennislive.de/?L1=Public&L2=Verein&L2P=2294&Page=Spielbetrieb&Sportart=96&Saison=2025"

    try:
        saved_file = fetch_website_source(url)
        print(f"\nSuccess! Website source code saved to: {saved_file}")

        # Read the saved content and extract links
        with open(saved_file, 'r', encoding='utf-8') as f:
            content = f.read()

        team_roster_links, ranking_table_links = extract_team_links(content)

        print(f"\n{'='*60}")
        print("EXTRACTED LINKS:")
        print(f"{'='*60}")

        # Add root URL to team roster links
        root_url = "https://leipzig.tischtennislive.de/"
        full_team_roster_links = [f"{root_url}{link}" for link in team_roster_links]

        # Define experiment directory for later use
        experiment_dir = "experiment"

        print(f"\nTeam Roster Links ({len(full_team_roster_links)} found):")
        for i, link in enumerate(full_team_roster_links, 1):
            print(f"  {i}. {link}")

        print(f"\nRanking Table Links ({len(ranking_table_links)} found):")
        for i, link in enumerate(ranking_table_links, 1):
            print(f"  {i}. {link}")

        print(f"\n{'='*60}")
        print("FETCHING TEAM ROSTER SOURCES:")
        print(f"{'='*60}")

        # Fetch the source code of each team roster page
        saved_roster_files = fetch_team_roster_sources(full_team_roster_links)

        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}")
        print(f"Team Roster Links Found: {len(full_team_roster_links)}")
        print(f"Ranking Table Links Generated: {len(ranking_table_links)}")
        print(f"Team Roster Source Files Downloaded: {len(saved_roster_files)}")
        print(f"\nFiles saved to: {experiment_dir}/")
        print(f"{'='*60}")

        # Extract team names and divisions from the main content
        teams_info = extract_team_names_and_divisions(content)

        # Fetch ranking table pages
        print(f"\n{'='*60}")
        print("FETCHING RANKING TABLE SOURCES:")
        print(f"{'='*60}")

        saved_ranking_files = fetch_ranking_table_sources(ranking_table_links, teams_info, experiment_dir)

        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}")
        print(f"Team Roster Links Found: {len(full_team_roster_links)}")
        print(f"Ranking Table Links Generated: {len(ranking_table_links)}")
        print(f"Team Roster Source Files Downloaded: {len(saved_roster_files)}")
        print(f"Ranking Table Source Files Downloaded: {len(saved_ranking_files)}")
        print(f"\nFiles saved to: {experiment_dir}/")
        print(f"{'='*60}")

        # Extract ranking data from ranking table files
        print(f"\n{'='*60}")
        print("EXTRACTING RANKING DATA:")
        print(f"{'='*60}")

        ranking_data = extract_ranking_data_from_pages(experiment_dir, teams_info)

        # Display extracted ranking data
        total_teams = 0
        for division_name in sorted(ranking_data.keys()):
            division_info = ranking_data[division_name]
            teams = division_info['teams']
            total_teams += len(teams)

            print(f"\n{division_name}:")
            print("-" * 60)
            print(f"  Total teams: {len(teams)}")

            for i, team in enumerate(teams, 1):
                print(f"    {i:2d}. {team['team_name']:<30} -> {team['roster_link']}")

        print(f"\n{'='*60}")
        print("RANKING DATA SUMMARY:")
        print(f"{'='*60}")
        print(f"Divisions processed: {len(ranking_data)}")
        print(f"Total teams found: {total_teams}")
        print(f"{'='*60}")

        # Fetch all team rosters from all divisions
        print(f"\n{'='*60}")
        print("FETCHING ALL TEAM ROSTERS:")
        print(f"{'='*60}")

        all_team_rosters = fetch_all_team_rosters(ranking_data, experiment_dir)

        # Display summary of fetched team rosters
        total_fetched_teams = 0
        for division_name in sorted(all_team_rosters.keys()):
            teams = all_team_rosters[division_name]
            total_fetched_teams += len(teams)

            print(f"\n{division_name}:")
            print("-" * 60)
            print(f"  Fetched teams: {len(teams)}")

            for i, team in enumerate(teams, 1):
                print(f"    {i:2d}. {team['team_name']:<30} -> {team['file_path']}")

        print(f"\n{'='*60}")
        print("TEAM ROSTER FETCHING SUMMARY:")
        print(f"{'='*60}")
        print(f"Divisions processed: {len(all_team_rosters)}")
        print(f"Total team rosters fetched: {total_fetched_teams}")
        print(f"{'='*60}")

        # Extract match data from all roster files
        print(f"\n{'='*60}")
        print("EXTRACTING MATCH DATA:")
        print(f"{'='*60}")

        matches_data = extract_match_data_from_rosters(experiment_dir)

        # Display extracted match data with actual team names
        total_matches = 0
        completed_matches = 0
        upcoming_matches = 0

        for team_id in sorted(matches_data.keys()):
            matches = matches_data[team_id]
            total_matches += len(matches)

            # Count completed and upcoming matches
            for match in matches:
                if match.get('status') == 'completed':
                    completed_matches += 1
                else:
                    upcoming_matches += 1

            # Get team name and division
            if team_id in teams_info:
                team_name, division_name = teams_info[team_id]
                team_display = f"{team_name} / {division_name}"
            else:
                team_display = f"Team {team_id}"

            print(f"\n{team_display} ({len(matches)} matches):")
            print("-" * 60)

            # Separate completed and upcoming matches
            completed = [m for m in matches if m.get('status') == 'completed']
            upcoming = [m for m in matches if m.get('status') == 'upcoming']

            if completed:
                print("  Completed matches:")
                for i, match in enumerate(completed, 1):
                    score = f"{match.get('home_score', '')}:{match.get('guest_score', '')}" if match.get('home_score') and match.get('guest_score') else 'N/A'
                    print(f"    {i:2d}. {match.get('date', '')} {match.get('time', '')} - {match.get('home_team', '')} vs {match.get('guest_team', '')} ({score})")

            if upcoming:
                print("  Upcoming matches:")
                for i, match in enumerate(upcoming, 1):
                    print(f"    {i:2d}. {match.get('date', '')} {match.get('time', '')} - {match.get('home_team', '')} vs {match.get('guest_team', '')}")

        print(f"\n{'='*60}")
        print("MATCH DATA SUMMARY:")
        print(f"{'='*60}")
        print(f"Teams with matches: {len(matches_data)}")
        print(f"Total matches found: {total_matches}")
        print(f"Completed matches: {completed_matches}")
        print(f"Upcoming matches: {upcoming_matches}")
        print(f"{'='*60}")

        # Extract player data from all roster files
        print(f"\n{'='*60}")
        print("EXTRACTING PLAYER DATA:")
        print(f"{'='*60}")

        players_data = extract_player_data_from_rosters(experiment_dir)

        # Display extracted player data with actual team names
        total_players = 0
        for team_id in sorted(players_data.keys()):
            players = players_data[team_id]
            total_players += len(players)

            # Get team name and division
            if team_id in teams_info:
                team_name, division_name = teams_info[team_id]
                team_display = f"{team_name} / {division_name}"
            else:
                team_display = f"Team {team_id}"

            print(f"\n{team_display} ({len(players)} players):")
            print("-" * 60)
            for i, (player_name, live_pz) in enumerate(players, 1):
                print(f"  {i:2d}. {player_name:<35} LivePZ: {live_pz}")

        print(f"\n{'='*60}")
        print("PLAYER DATA SUMMARY:")
        print(f"{'='*60}")
        print(f"Teams processed: {len(players_data)}")
        print(f"Total players found: {total_players}")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\nFailed to fetch website source: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())