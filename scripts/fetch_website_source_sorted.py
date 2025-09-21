#!/usr/bin/env python3
"""
Script to fetch the source code of a website and save it to the experiment directory.
Compatible with Python 3.13.7
"""

import urllib.request
import urllib.error
import os
import re
import json
from datetime import datetime, timedelta


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

        # Ensure data directory exists
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)

        # Full path for output file
        output_path = os.path.join(data_dir, output_filename)

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


def fetch_team_roster_sources(team_roster_links: list[str], data_dir: str = "data") -> list[str]:
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

            # Create division subfolder - use a default name since we don't have division info here
            division_folder = os.path.join(data_dir, "team_rosters")
            os.makedirs(division_folder, exist_ok=True)

            # Full path for output file in division subfolder
            output_path = os.path.join(division_folder, filename)

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


def fetch_ranking_table_sources(ranking_table_links: list[str], teams_info: dict, data_dir: str = "data") -> list[str]:
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

            # Create division subfolder if we have division info
            division_folder = data_dir
            if div_id in teams_info:
                team_name, division_name = teams_info[div_id]
                # Clean division name for folder name
                clean_division_name = re.sub(r'[^\w\s-]', '', division_name).strip()
                clean_division_name = re.sub(r'[-\s]+', '_', clean_division_name)
                division_folder = os.path.join(data_dir, clean_division_name)
                os.makedirs(division_folder, exist_ok=True)

            # Full path for output file
            output_path = os.path.join(division_folder, filename)

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


def extract_ranking_data_from_pages(data_dir: str = "data", teams_info: dict = None) -> dict:
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
    ranking_files = glob.glob(os.path.join(data_dir, "**", "ranking_table_*.html"), recursive=True)

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


def fetch_all_team_rosters(ranking_data: dict, data_dir: str = "data") -> dict:
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

                # Create division subfolder
                division_folder = os.path.join(data_dir, clean_division_name)
                os.makedirs(division_folder, exist_ok=True)

                # Full path for output file in division subfolder
                output_path = os.path.join(division_folder, filename)

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


def extract_match_data_from_rosters(data_dir: str = "data") -> dict:
    """
    Extract match data from all team roster HTML files.

    Args:
        experiment_dir: Directory containing the team roster HTML files

    Returns:
        Dictionary with team IDs as keys and list of match dictionaries as values
    """
    import glob

    # Find all team roster files
    roster_files = glob.glob(os.path.join(data_dir, "**", "team_roster_*.html"), recursive=True)

    all_matches_data = {}

    for roster_file in roster_files:
        try:
            # Extract team ID from filename - handle both old and new naming patterns
            filename = os.path.basename(roster_file)
            team_id = None

            # Try new naming pattern first: team_roster_{division}_{team_name}_{team_id}.html
            new_pattern = r'team_roster_[^_]+_[^_]+_(\d+)\.html'
            team_id_match = re.search(new_pattern, filename)
            if team_id_match:
                team_id = team_id_match.group(1)
            else:
                # Fallback to old naming pattern: team_roster_L2P_{team_id}.html
                old_pattern = r'team_roster_L2P_(\d+)\.html'
                team_id_match = re.search(old_pattern, filename)
                if team_id_match:
                    team_id = team_id_match.group(1)

            if not team_id:
                continue

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
                                # No score found, this is an upcoming match
                                match_info['status'] = 'upcoming'
                                match_info['home_score'] = ''
                                match_info['guest_score'] = ''
                        else:
                            # No content in score column, this is an upcoming match
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


def extract_player_data_from_rosters(data_dir: str = "data") -> dict:
    """
    Extract player names and LivePZ values from all team roster HTML files.

    Args:
        experiment_dir: Directory containing the team roster HTML files

    Returns:
        Dictionary with team IDs as keys and list of (player_name, live_pz) tuples as values
    """
    import glob

    # Find all team roster files - handle both old and new naming patterns
    roster_files = glob.glob(os.path.join(data_dir, "**", "team_roster_*.html"), recursive=True)

    all_players_data = {}

    for roster_file in roster_files:
        try:
            # Extract team ID from filename - handle both old and new naming patterns
            filename = os.path.basename(roster_file)
            team_id = None

            # Try new naming pattern first: team_roster_{division}_{team_name}_{team_id}.html
            new_pattern = r'team_roster_[^_]+_[^_]+_(\d+)\.html'
            team_id_match = re.search(new_pattern, filename)
            if team_id_match:
                team_id = team_id_match.group(1)
            else:
                # Fallback to old naming pattern: team_roster_L2P_{team_id}.html
                old_pattern = r'team_roster_L2P_(\d+)\.html'
                team_id_match = re.search(old_pattern, filename)
                if team_id_match:
                    team_id = team_id_match.group(1)

            if not team_id:
                continue

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


def extract_club_links_from_rosters(data_dir: str = "data") -> dict:
    """
    Extract club links from all team roster HTML files.

    Args:
        data_dir: Directory containing the team roster HTML files

    Returns:
        Dictionary with team IDs as keys and club information as values
    """
    import glob

    # Find all team roster files - handle both old and new naming patterns
    roster_files = glob.glob(os.path.join(data_dir, "**", "team_roster_*.html"), recursive=True)

    club_data = {}

    for roster_file in roster_files:
        try:
            # Extract team ID from filename - handle both old and new naming patterns
            filename = os.path.basename(roster_file)
            team_id = None

            # Try new naming pattern first: team_roster_{division}_{team_name}_{team_id}.html
            new_pattern = r'team_roster_[^_]+_[^_]+_(\d+)\.html'
            team_id_match = re.search(new_pattern, filename)
            if team_id_match:
                team_id = team_id_match.group(1)
            else:
                # Fallback to old naming pattern: team_roster_L2P_{team_id}.html
                old_pattern = r'team_roster_L2P_(\d+)\.html'
                team_id_match = re.search(old_pattern, filename)
                if team_id_match:
                    team_id = team_id_match.group(1)

            if not team_id:
                continue

            # Read the HTML content
            with open(roster_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract club link from the navigation
            # Pattern: <a aria-haspopup="true" href="?L1=Public&L2=Verein&L2P={club_id}&Page=Spielbetrieb&Sportart=96" >Verein</a>
            club_pattern = r'href="([^"]*L2=Verein[^"]*)"[^>]*>Verein</a>'
            club_match = re.search(club_pattern, content, re.IGNORECASE)

            if club_match:
                club_link = club_match.group(1)
                # Extract club ID from the link
                club_id_match = re.search(r'L2P=([^&]+)', club_link)
                if club_id_match:
                    club_id = club_id_match.group(1)
                    club_data[team_id] = {
                        'club_id': club_id,
                        'club_link': club_link,
                        'team_file': roster_file
                    }
                    print(f"  Extracted club {club_id} for team {team_id}")

        except Exception as e:
            print(f"  Error processing {roster_file}: {e}")

    return club_data


def fetch_club_overview_sources(club_data: dict, data_dir: str = "data") -> dict:
    """
    Fetch the source code of each club overview page and save to data directory.

    Args:
        club_data: Dictionary with team IDs as keys and club information as values
        data_dir: Directory to save the files

    Returns:
        Dictionary with club IDs as keys and file paths as values
    """
    saved_files = {}
    root_url = "https://leipzig.tischtennislive.de/"

    # Get unique club IDs
    unique_club_ids = set()
    for team_id, club_info in club_data.items():
        unique_club_ids.add(club_info['club_id'])

    print(f"Fetching {len(unique_club_ids)} unique club overview pages...")

    for i, club_id in enumerate(unique_club_ids, 1):
        try:
            # Build club overview URL
            club_url = f"{root_url}?L1=Public&L2=Verein&L2P={club_id}&Page=Spielbetrieb&Sportart=96"

            print(f"Fetching club overview {i}/{len(unique_club_ids)}: {club_url}")

            # Create request with headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            req = urllib.request.Request(club_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8')

            # Generate filename based on club ID
            filename = f"club_overview_{club_id}.html"

            # Create clubs subfolder
            clubs_folder = os.path.join(data_dir, "clubs")
            os.makedirs(clubs_folder, exist_ok=True)

            # Full path for output file
            output_path = os.path.join(clubs_folder, filename)

            # Save content to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            saved_files[club_id] = output_path
            print(f"  Saved to: {output_path}")

        except urllib.error.HTTPError as e:
            print(f"  HTTP Error {e.code}: {e.reason} for club {club_id}")
        except urllib.error.URLError as e:
            print(f"  URL Error: {e.reason} for club {club_id}")
        except Exception as e:
            print(f"  Unexpected error: {e} for club {club_id}")

    return saved_files


def extract_all_teams_from_clubs(club_files: dict, data_dir: str = "data") -> dict:
    """
    Extract all teams from each club overview page using the same method as the main page.

    Args:
        club_files: Dictionary with club IDs as keys and file paths as values
        data_dir: Directory containing the files

    Returns:
        Dictionary with club IDs as keys and list of team information as values
    """
    all_club_teams = {}

    print(f"Extracting teams from {len(club_files)} club overview pages...")

    for club_id, club_file in club_files.items():
        try:
            # Read the HTML content
            with open(club_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use the existing extract_team_names_and_divisions function
            # to extract teams from the club page (same structure as main page)
            teams_info = extract_team_names_and_divisions(content)

            if teams_info:
                teams = []
                for team_id, (team_name, division_name) in teams_info.items():
                    # Build the team roster link based on the team ID
                    # This follows the same pattern as the original links
                    team_link = f"?L1=Ergebnisse&L2=TTStaffeln&L2P={team_id}&L3=Mannschaften&L3P={team_id}"

                    teams.append({
                        'team_name': team_name,
                        'team_id': team_id,
                        'team_link': team_link,
                        'division': division_name
                    })

                all_club_teams[club_id] = teams
                print(f"  Extracted {len(teams)} teams from club {club_id}")
                for team in teams:
                    print(f"    - {team['team_name']} (ID: {team['team_id']})")
            else:
                print(f"  No teams found in club {club_id}")

        except Exception as e:
            print(f"  Error processing club {club_id}: {e}")

    return all_club_teams


def fetch_all_club_teams(club_teams: dict, data_dir: str = "data") -> dict:
    """
    Fetch all team rosters from all clubs.

    Args:
        club_teams: Dictionary with club IDs as keys and list of team information as values
        data_dir: Directory to save the team roster files

    Returns:
        Dictionary with all team roster information organized by club
    """
    root_url = "https://leipzig.tischtennislive.de/"
    all_club_team_rosters = {}

    total_teams = 0
    for club_id, teams in club_teams.items():
        total_teams += len(teams)

    print(f"Preparing to fetch {total_teams} team rosters from {len(club_teams)} clubs...")

    for club_id, teams in club_teams.items():
        club_rosters = []

        for i, team in enumerate(teams, 1):
            try:
                team_link = team['team_link']

                # Add root URL if not present
                if not team_link.startswith('http'):
                    full_url = f"{root_url}{team_link}"
                else:
                    full_url = team_link

                print(f"  Fetching team roster {i}/{len(teams)} in club {club_id}: {team['team_name']}")

                # Create request with headers to mimic a browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                req = urllib.request.Request(full_url, headers=headers)
                with urllib.request.urlopen(req) as response:
                    content = response.read().decode('utf-8')

                # Generate filename based on team name and club
                clean_team_name = re.sub(r'[^\w\s-]', '', team['team_name']).strip()
                clean_team_name = re.sub(r'[-\s]+', '_', clean_team_name)

                team_id = team.get('team_id', 'unknown')
                filename = f"club_team_{club_id}_{clean_team_name}_{team_id}.html"

                # Create club teams subfolder
                club_teams_folder = os.path.join(data_dir, "club_teams")
                os.makedirs(club_teams_folder, exist_ok=True)

                # Full path for output file
                output_path = os.path.join(club_teams_folder, filename)

                # Save content to file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Store team information
                club_rosters.append({
                    'team_name': team['team_name'],
                    'team_id': team_id,
                    'team_link': team_link,
                    'file_path': output_path
                })

                print(f"    Saved to: {output_path}")

            except urllib.error.HTTPError as e:
                print(f"    HTTP Error {e.code}: {e.reason} for {full_url}")
            except urllib.error.URLError as e:
                print(f"    URL Error: {e.reason} for {full_url}")
            except Exception as e:
                print(f"    Unexpected error: {e} for {full_url}")

        if club_rosters:
            all_club_team_rosters[club_id] = club_rosters

    return all_club_team_rosters


def map_teams_to_clubs(club_data: dict, club_teams: dict) -> dict:
    """
    Create a mapping between teams and their clubs.

    Args:
        club_data: Dictionary with team IDs as keys and club information as values
        club_teams: Dictionary with club IDs as keys and list of team information as values

    Returns:
        Dictionary with team IDs as keys and club information as values
    """
    team_to_club_mapping = {}

    # Map teams to clubs based on club_data
    for team_id, club_info in club_data.items():
        club_id = club_info['club_id']
        team_to_club_mapping[team_id] = {
            'club_id': club_id,
            'club_link': club_info['club_link'],
            'team_file': club_info['team_file']
        }

    # Add additional teams from club overviews that weren't in the original data
    for club_id, teams in club_teams.items():
        for team in teams:
            team_id = team.get('team_id')
            if team_id and team_id not in team_to_club_mapping:
                team_to_club_mapping[team_id] = {
                    'club_id': club_id,
                    'team_link': team['team_link'],
                    'additional_team': True
                }

    return team_to_club_mapping


def update_match_tracking_with_club_teams(tracking_data: dict, team_to_club_mapping: dict, matches_data: dict) -> dict:
    """
    Update match tracking to include club information for all teams.

    Args:
        tracking_data: Current tracking data
        team_to_club_mapping: Mapping between teams and clubs
        matches_data: Match data for all teams (used for reference)

    Returns:
        Updated tracking data with club information
    """
    # Add club information to existing upcoming matches
    # Note: The comprehensive upcoming matches already include club team matches
    # from the extract_upcoming_matches_from_data function, so we just need to
    # add club metadata to existing matches
    for match in tracking_data.get("upcoming_matches", []):
        team_id = match.get("team_id")
        if team_id and team_id in team_to_club_mapping:
            club_info = team_to_club_mapping[team_id]
            match["club_id"] = club_info.get("club_id")
            match["club_team"] = club_info.get("additional_team", False)

    # Note: We don't add additional matches here because they are already
    # included in the comprehensive upcoming_matches from extract_upcoming_matches_from_data

    return tracking_data


def load_match_tracking_data(data_dir: str = "data") -> dict:
    """
    Load existing match tracking data from JSON file.

    Args:
        data_dir: Directory containing the JSON file

    Returns:
        Dictionary with match tracking data
    """
    json_file = os.path.join(data_dir, "match_tracking.json")

    if os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not load existing match tracking data: {e}")

    # Return default structure if file doesn't exist or is corrupted
    return {
        "last_scrape": None,
        "divisions": {},
        "upcoming_matches": []
    }


def save_match_tracking_data(tracking_data: dict, data_dir: str = "data") -> None:
    """
    Save match tracking data to JSON file.

    Args:
        tracking_data: Dictionary with match tracking data
        data_dir: Directory to save the JSON file
    """
    json_file = os.path.join(data_dir, "match_tracking.json")

    # Update last scrape timestamp
    tracking_data["last_scrape"] = datetime.now().isoformat()

    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(tracking_data, f, indent=2, ensure_ascii=False)
        print(f"Match tracking data saved to: {json_file}")
    except Exception as e:
        print(f"Error saving match tracking data: {e}")


def should_rescrape_division(division_name: str, tracking_data: dict) -> bool:
    """
    Determine if a division should be rescraped based on upcoming matches.

    Args:
        division_name: Name of the division to check
        tracking_data: Current tracking data

    Returns:
        True if division should be rescraped
    """
    if not tracking_data.get("upcoming_matches"):
        return True  # No tracking data, scrape everything

    # Get the last scrape time
    last_scrape_str = tracking_data.get("last_scrape")
    if not last_scrape_str:
        return True  # No last scrape time, scrape everything

    try:
        last_scrape_time = datetime.fromisoformat(last_scrape_str)
    except ValueError:
        return True  # Invalid last scrape time, scrape everything

    current_time = datetime.now()

    # Check if there are any upcoming matches in this division scheduled within the next 2 hours from last scrape
    for match in tracking_data["upcoming_matches"]:
        if match.get("division") == division_name:
            match_date_str = match.get("date", "")
            match_time_str = match.get("time", "")

            if match_date_str and match_time_str:
                try:
                    # Parse match date and time
                    match_datetime_str = f"{match_date_str} {match_time_str}"
                    match_datetime = datetime.strptime(match_datetime_str, "%d.%m.%Y %H:%M")

                    # If match is scheduled within the next 2 hours from last scrape, rescrape
                    if last_scrape_time <= match_datetime <= last_scrape_time + timedelta(hours=2):
                        return True
                except ValueError:
                    # If date parsing fails, be safe and rescrape
                    return True

    return False


def extract_upcoming_matches_from_data(matches_data: dict, teams_info: dict, team_to_club_mapping: dict = None) -> list:
    """
    Extract upcoming matches from match data for tracking.

    Args:
        matches_data: Dictionary with match data by team ID
        teams_info: Dictionary mapping team IDs to (team_name, division_name)
        team_to_club_mapping: Optional mapping of teams to clubs for additional teams

    Returns:
        List of upcoming matches with division and timestamp info
    """
    upcoming_matches = []

    for team_id, matches in matches_data.items():
        # Try to get team info from the original teams_info first
        team_name = None
        division_name = None

        if team_id in teams_info:
            team_name, division_name = teams_info[team_id]
        elif team_to_club_mapping and team_id in team_to_club_mapping:
            # This is a club team, try to get info from club data
            club_info = team_to_club_mapping[team_id]
            # For club teams, we might not have the exact team name, so use a generic name
            team_name = f"Club Team {team_id}"
            division_name = "Unknown"  # Club teams might not have division info

        # If we still don't have team info, skip this team
        if not team_name or not division_name:
            continue

        for match in matches:
            if match.get("status") == "upcoming":
                upcoming_matches.append({
                    "team_id": team_id,
                    "team_name": team_name,
                    "division": division_name,
                    "date": match.get("date", ""),
                    "time": match.get("time", ""),
                    "home_team": match.get("home_team", ""),
                    "guest_team": match.get("guest_team", "")
                })

    return upcoming_matches


def main():
    """Main function to run the script."""
    url = "https://leipzig.tischtennislive.de/?L1=Public&L2=Verein&L2P=2294&Page=Spielbetrieb&Sportart=96&Saison=2025"

    # Initialize variables
    divisions_to_scrape = set()

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

        # Define data directory for later use
        data_dir = "data"

        print(f"\nTeam Roster Links ({len(full_team_roster_links)} found):")
        for i, link in enumerate(full_team_roster_links, 1):
            print(f"  {i}. {link}")

        print(f"\nRanking Table Links ({len(ranking_table_links)} found):")
        for i, link in enumerate(ranking_table_links, 1):
            print(f"  {i}. {link}")

        print(f"\n{'='*60}")
        print("FETCHING TEAM ROSTER SOURCES:")
        print(f"{'='*60}")

        # Fetch the source code of each team roster page (fetch all initially)
        print("Fetching all team roster sources for complete data...")
        saved_roster_files = fetch_team_roster_sources(full_team_roster_links, data_dir)

        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}")
        print(f"Team Roster Links Found: {len(full_team_roster_links)}")
        print(f"Ranking Table Links Generated: {len(ranking_table_links)}")
        print(f"Team Roster Source Files Downloaded: {len(saved_roster_files)}")
        print(f"\nFiles saved to: {data_dir}/")
        print(f"{'='*60}")

        # Extract team names and divisions from the main content
        teams_info = extract_team_names_and_divisions(content)

        # Fetch ranking table pages (only for divisions that need rescraping)
        print(f"\n{'='*60}")
        print("FETCHING RANKING TABLE SOURCES:")
        print(f"{'='*60}")

        if divisions_to_scrape:
            # Filter ranking table links to only include divisions that need rescraping
            filtered_ranking_links = []
            for link in ranking_table_links:
                # Extract division ID from the link
                division_id = re.search(r'L2P=([^&]+)', link)
                if division_id:
                    div_id = division_id.group(1)
                    # Get division name from teams_info
                    if div_id in teams_info:
                        team_name, division_name = teams_info[div_id]
                        if division_name in divisions_to_scrape:
                            filtered_ranking_links.append(link)

            print(f"Fetching ranking tables for {len(filtered_ranking_links)} divisions that need rescraping...")
            saved_ranking_files = fetch_ranking_table_sources(filtered_ranking_links, teams_info, data_dir)
        else:
            print("No divisions need rescraping, but fetching all ranking tables for complete data...")
            saved_ranking_files = fetch_ranking_table_sources(ranking_table_links, teams_info, data_dir)

        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}")
        print(f"Team Roster Links Found: {len(full_team_roster_links)}")
        print(f"Ranking Table Links Generated: {len(ranking_table_links)}")
        print(f"Team Roster Source Files Downloaded: {len(saved_roster_files)}")
        print(f"Ranking Table Source Files Downloaded: {len(saved_ranking_files)}")
        print(f"\nFiles saved to: {data_dir}/")
        print(f"{'='*60}")

        # Extract ranking data from ranking table files
        print(f"\n{'='*60}")
        print("EXTRACTING RANKING DATA:")
        print(f"{'='*60}")

        # Filter teams_info to only include divisions that need rescraping
        if divisions_to_scrape:
            filtered_teams_info = {team_id: (team_name, div_name) for team_id, (team_name, div_name) in teams_info.items() if div_name in divisions_to_scrape}
            print(f"Extracting ranking data for {len(divisions_to_scrape)} divisions that need rescraping...")
        else:
            filtered_teams_info = teams_info
            print("Extracting ranking data for all divisions...")

        ranking_data = extract_ranking_data_from_pages(data_dir, filtered_teams_info)

        # Load existing match tracking data
        tracking_data = load_match_tracking_data(data_dir)

        # Check which divisions need rescraping based on upcoming matches
        divisions_to_scrape = set()
        for division_name in ranking_data.keys():
            if should_rescrape_division(division_name, tracking_data):
                divisions_to_scrape.add(division_name)

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

        # Fetch team rosters from divisions that need rescraping
        print(f"\n{'='*60}")
        print("FETCHING TEAM ROSTERS:")
        print(f"{'='*60}")

        # Filter ranking data to only include divisions that need rescraping
        if divisions_to_scrape:
            filtered_ranking_data = {div: ranking_data[div] for div in divisions_to_scrape if div in ranking_data}
            print(f"Fetching team rosters from {len(filtered_ranking_data)} divisions that need rescraping...")
        else:
            filtered_ranking_data = ranking_data
            print("No divisions need rescraping, but fetching all team rosters for complete data...")

        all_team_rosters = fetch_all_team_rosters(filtered_ranking_data, data_dir)

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

        if divisions_to_scrape:
            print(f"\n{'='*60}")
            print("DIVISIONS TO RESCRAPE:")
            print(f"{'='*60}")
            for division in sorted(divisions_to_scrape):
                print(f"  {division}")
            print(f"{'='*60}")

        # Extract club links from ALL team roster files in the entire data directory
        print(f"\n{'='*60}")
        print("EXTRACTING CLUB LINKS FROM ALL TEAM ROSTERS:")
        print(f"{'='*60}")

        # Find all team roster files in the entire data directory (including subfolders)
        import glob
        all_roster_files = glob.glob(os.path.join(data_dir, "**", "team_roster_*.html"), recursive=True)
        print(f"Found {len(all_roster_files)} team roster files to process for club links...")

        club_data = {}
        processed_count = 0
        skipped_count = 0

        for roster_file in all_roster_files:
            try:
                # Extract team ID from filename - handle both old and new naming patterns
                filename = os.path.basename(roster_file)
                team_id = None

                # Try new naming pattern first: team_roster_{division}_{team_name}_{team_id}.html
                new_pattern = r'team_roster_[^_]+_[^_]+_(\d+)\.html'
                team_id_match = re.search(new_pattern, filename)
                if team_id_match:
                    team_id = team_id_match.group(1)
                else:
                    # Fallback to old naming pattern: team_roster_L2P_{team_id}.html
                    old_pattern = r'team_roster_L2P_(\d+)\.html'
                    team_id_match = re.search(old_pattern, filename)
                    if team_id_match:
                        team_id = team_id_match.group(1)

                # If we can't extract team ID from filename, try to extract it from the HTML content
                if not team_id:
                    try:
                        with open(roster_file, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Try to extract team ID from the HTML content using the roster link pattern
                        team_id_pattern = r'L3P=([^&"]+)'
                        team_id_match = re.search(team_id_pattern, content)
                        if team_id_match:
                            team_id = team_id_match.group(1)
                    except:
                        pass

                if not team_id:
                    skipped_count += 1
                    continue

                # Read the HTML content
                with open(roster_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract club link from the navigation
                # Pattern: <a aria-haspopup="true" href="?L1=Public&L2=Verein&L2P={club_id}&Page=Spielbetrieb&Sportart=96" >Verein</a>
                club_pattern = r'href="([^"]*L2=Verein[^"]*)"[^>]*>Verein</a>'
                club_match = re.search(club_pattern, content, re.IGNORECASE)

                if club_match:
                    club_link = club_match.group(1)
                    # Extract club ID from the link
                    club_id_match = re.search(r'L2P=([^&]+)', club_link)
                    if club_id_match:
                        club_id = club_id_match.group(1)
                        club_data[team_id] = {
                            'club_id': club_id,
                            'club_link': club_link,
                            'team_file': roster_file
                        }
                        print(f"  Extracted club {club_id} for team {team_id}")
                        processed_count += 1

            except Exception as e:
                print(f"  Error processing {roster_file}: {e}")

        print(f"Successfully processed {processed_count} team roster files for club links")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} files (could not extract team ID)")

        # Display extracted club data
        unique_clubs = set()
        for team_id, club_info in club_data.items():
            unique_clubs.add(club_info['club_id'])

        print(f"\nFound {len(club_data)} teams with club information:")
        print(f"Unique clubs discovered: {len(unique_clubs)}")
        for team_id in sorted(club_data.keys()):
            club_info = club_data[team_id]
            print(f"  Team {team_id} -> Club {club_info['club_id']}")

        print(f"\n{'='*60}")
        print("CLUB DATA SUMMARY:")
        print(f"{'='*60}")
        print(f"Teams with club data: {len(club_data)}")
        print(f"Unique clubs found: {len(unique_clubs)}")
        print(f"{'='*60}")

        # Fetch club overview pages for ALL clubs
        print(f"\n{'='*60}")
        print("FETCHING ALL CLUB OVERVIEW PAGES:")
        print(f"{'='*60}")

        club_files = fetch_club_overview_sources(club_data, data_dir)

        print(f"\n{'='*60}")
        print("CLUB OVERVIEW SUMMARY:")
        print(f"{'='*60}")
        print(f"Club overview pages fetched: {len(club_files)}")
        print(f"{'='*60}")

        # Extract all teams from ALL club overviews
        print(f"\n{'='*60}")
        print("EXTRACTING ALL TEAMS FROM ALL CLUBS:")
        print(f"{'='*60}")

        club_teams = extract_all_teams_from_clubs(club_files, data_dir)

        # Display extracted club teams
        total_club_teams = 0
        for club_id in sorted(club_teams.keys()):
            teams = club_teams[club_id]
            total_club_teams += len(teams)

            print(f"\nClub {club_id}:")
            print("-" * 60)
            print(f"  Total teams: {len(teams)}")

            for i, team in enumerate(teams, 1):
                print(f"    {i:2d}. {team['team_name']:<30} (ID: {team.get('team_id', 'N/A')})")

        print(f"\n{'='*60}")
        print("CLUB TEAMS SUMMARY:")
        print(f"{'='*60}")
        print(f"Clubs processed: {len(club_teams)}")
        print(f"Total teams found: {total_club_teams}")
        print(f"{'='*60}")

        # Fetch team rosters for all teams from all clubs
        print(f"\n{'='*60}")
        print("FETCHING ALL CLUB TEAM ROSTERS:")
        print(f"{'='*60}")

        all_club_team_rosters = fetch_all_club_teams(club_teams, data_dir)

        # Display summary of fetched club team rosters
        total_fetched_club_teams = 0
        for club_id in sorted(all_club_team_rosters.keys()):
            teams = all_club_team_rosters[club_id]
            total_fetched_club_teams += len(teams)

            print(f"\nClub {club_id}:")
            print("-" * 60)
            print(f"  Fetched teams: {len(teams)}")

            for i, team in enumerate(teams, 1):
                print(f"    {i:2d}. {team['team_name']:<30} -> {team['file_path']}")

        print(f"\n{'='*60}")
        print("CLUB TEAM ROSTER FETCHING SUMMARY:")
        print(f"{'='*60}")
        print(f"Clubs processed: {len(all_club_team_rosters)}")
        print(f"Total club team rosters fetched: {total_fetched_club_teams}")
        print(f"{'='*60}")

        # Create comprehensive team-to-club mapping
        print(f"\n{'='*60}")
        print("CREATING COMPREHENSIVE TEAM-TO-CLUB MAPPING:")
        print(f"{'='*60}")

        team_to_club_mapping = map_teams_to_clubs(club_data, club_teams)

        print(f"\nTeam-to-club mapping created for {len(team_to_club_mapping)} teams:")
        for team_id in sorted(team_to_club_mapping.keys()):
            mapping_info = team_to_club_mapping[team_id]
            additional = " (additional)" if mapping_info.get("additional_team") else ""
            print(f"  Team {team_id} -> Club {mapping_info['club_id']}{additional}")

        print(f"\n{'='*60}")
        print("MAPPING SUMMARY:")
        print(f"{'='*60}")
        print(f"Total teams mapped: {len(team_to_club_mapping)}")
        print(f"{'='*60}")

        # Extract match data from all roster files (including club teams)
        print(f"\n{'='*60}")
        print("EXTRACTING MATCH DATA FROM ALL ROSTERS:")
        print(f"{'='*60}")

        # Extract match data from main team rosters
        matches_data = extract_match_data_from_rosters(data_dir)

        # Extract match data from club team rosters
        club_matches_data = extract_match_data_from_rosters(os.path.join(data_dir, "club_teams"))

        # Combine all match data
        all_matches_data = {**matches_data, **club_matches_data}

        # Extract upcoming matches for tracking from all sources
        upcoming_matches = extract_upcoming_matches_from_data(all_matches_data, teams_info, team_to_club_mapping)

        # Update tracking data with new upcoming matches (including club teams)
        tracking_data["upcoming_matches"] = upcoming_matches

        # Save updated tracking data
        save_match_tracking_data(tracking_data, data_dir)

        # Display extracted match data with actual team names
        total_matches = 0
        completed_matches = 0
        upcoming_matches_count = 0

        for team_id in sorted(all_matches_data.keys()):
            matches = all_matches_data[team_id]
            total_matches += len(matches)

            # Count completed and upcoming matches
            for match in matches:
                if match.get('status') == 'completed':
                    completed_matches += 1
                else:
                    upcoming_matches_count += 1

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
        print(f"Teams with matches: {len(all_matches_data)}")
        print(f"Total matches found: {total_matches}")
        print(f"Completed matches: {completed_matches}")
        print(f"Upcoming matches: {upcoming_matches_count}")
        print(f"{'='*60}")

        # Display match tracking information
        print(f"\n{'='*60}")
        print("MATCH TRACKING SUMMARY:")
        print(f"{'='*60}")
        print(f"Last scrape: {tracking_data.get('last_scrape', 'Never')}")
        print(f"Upcoming matches tracked: {len(tracking_data.get('upcoming_matches', []))}")
        print(f"Match tracking data saved to: {os.path.join(data_dir, 'match_tracking.json')}")
        print(f"{'='*60}")


        # Extract player data from all roster files (including club teams)
        print(f"\n{'='*60}")
        print("EXTRACTING PLAYER DATA FROM ALL ROSTERS:")
        print(f"{'='*60}")

        # Extract player data from main team rosters
        players_data = extract_player_data_from_rosters(data_dir)

        # Extract player data from club team rosters
        club_players_data = extract_player_data_from_rosters(os.path.join(data_dir, "club_teams"))

        # Combine all player data
        all_players_data = {**players_data, **club_players_data}

        # Display extracted player data with actual team names
        total_players = 0
        for team_id in sorted(all_players_data.keys()):
            players = all_players_data[team_id]
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
        print(f"Teams processed: {len(all_players_data)}")
        print(f"Total players found: {total_players}")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\nFailed to fetch website source: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())