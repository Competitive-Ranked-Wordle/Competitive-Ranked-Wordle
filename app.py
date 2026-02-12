"""
Competitive Ranked Wordle
    A program to manage multi-player games of Wordle, processing scores, and calculating ELO rankings

Authors: Jivan RamjiSingh

TODO:
    P0:
    P1:
        - Add ELO and OpenSkill decay (pending rate determination)
    P2:
        - Lots of documentation

Copyright (C) 2025  Jivan RamjiSingh

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# ---
# Imports
# ---

import os
import yaml
import logging
import jwt
from typing import Annotated
from collections import defaultdict
from datetime import date, timedelta, timezone, datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel
from pydantic import BaseModel
from openskill.models import PlackettLuce

from bin.mariadb_handler import create_wordle_db, update_player_entry, update_score_entry, add_entry, get_entries, lookup_player, register_player, get_all_players
from bin.utilities import parse_score, get_wordle_puzzle, calculate_elo, match_player_name

# ---
# Data Definitions
# --

config_file = os.getenv('CONFIG_FILE', 'config.yml')
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

tz_eastern = ZoneInfo('America/New_York')

model = PlackettLuce()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY: str = config['security']['secret_key']
ALGORITHM: str = config['security']['algorithm']
ACCESS_TOKEN_EXPIRE_MINUTES: str = config['security']['token_expiration']
USERS: str = config['security']['users']

class Score(BaseModel):
    score: str
    uuid: str

class Player(BaseModel):
    player_name: str
    player_platform: str
    player_uuid: str

class BackfillData(BaseModel):
    start_puzzle: int
    end_puzzle: int
    calc_type: str

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str

# ---
# Library Configurations
# ---

logging.basicConfig(filename=config['log_file'], level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app = FastAPI()
if create_wordle_db(config):
    pass
else:
    raise(TypeError("DB Failed to Init Properly"))

# ---
# Helper Functions
# ---

def check_players(start: int, end: int, hard_mode: bool = True):
    """
    Checks if anyone played a given puzzle
    """
    if hard_mode:
        query_params = f"WHERE puzzle >= {start} and puzzle <= {end} AND hard_mode = 1"
    else:
        query_params = f"WHERE puzzle >= {start} and puzzle <= {end}"

    entries = get_entries(config, query_params)
    if entries == []:
        return False
    else:
        return True

def calculate_openskill(puzzle: int):
    """
    Calculate Openskill rankings for a given day
    """
    query_params = f"WHERE puzzle = {puzzle} AND hard_mode = 1"
    entries = get_entries(config, query_params)
    if len(entries) == 1:
        # Don't do calculations when only one player submits
        for entry in entries:
            player_data = lookup_player(config, player_id=entry['player_id'])
            score_data = {
                'mu': player_data['player_mu'],
                'sigma': player_data['player_sigma'],
                'ordinal': player_data['player_ord'],
                'ordinal_delta': 0
            }
            players_data = {
                'ord_delta': 0,
                'mu_delta': 0,
                'sigma_delta': 0
            }
            update_score_entry(config, entry['id'], score_data)
            update_player_entry(config, entry['player_id'], players_data)
        return False
    
    players = []
    scores = []
    player_stats = {}

    for entry in entries:
        player_data = lookup_player(config, player_id=entry['player_id'])
        players.append([model.rating(name=str(entry['player_id']), mu=player_data['player_mu'], sigma=player_data['player_sigma'])])
        scores.append(entry['calculated_score'])

        player_stats[entry['player_id']] = {
            'ordinal': player_data['player_ord'],
            'mu': player_data['player_mu'],
            'sigma': player_data['player_sigma']
        }

    match_scores = model.rate(players, scores=scores)

    i = 0
    for entry in entries:
        player = match_scores[i][0]

        score_data = {
            'sigma': player.sigma,
            'mu': player.mu,
            'ordinal': player.ordinal(),
            'ordinal_delta': player.ordinal() - player_stats[entry['player_id']]['ordinal']
        }

        players_data = {
            'player_mu': player.mu,
            'player_sigma': player.sigma,
            'player_ord': player.ordinal(),
            'ord_delta': player.ordinal() - player_stats[entry['player_id']]['ordinal'],
            'mu_delta': player.mu - player_stats[entry['player_id']]['mu'],
            'sigma_delta': player.sigma - player_stats[entry['player_id']]['sigma']
        }

        update_score_entry(config, entry['id'], score_data)
        update_player_entry(config, entry['player_id'], players_data)
        i += 1

def calculate_match_elo(puzzle: int):
    """
    Legacy ELO Calculation
    Translate rankings into 1-1 matches between each player, then sum the elo change
    """
    query_params = f"WHERE puzzle = {puzzle} AND hard_mode = 1"
    entries = get_entries(config, query_params)
    if len(entries) == 1:
        # Don't do calculations when only one player submits
        for entry in entries:
            player_data = lookup_player(config, player_id=entry['player_id'])
            score_data = {
                'elo': player_data['player_elo'],
                'elo_delta': 0,
            }
            players_data = {
                'elo_delta': 0
            }
            update_score_entry(config, entry['id'], score_data)
            update_player_entry(config, entry['player_id'], players_data)

        return False
    
    player_ids = []
    grouped = {i: [] for i in range(7)}  # Initialize keys 0 through 6
    for entry in entries:
        score = entry.get('calculated_score')
        grouped[score].append(entry)
        player_ids.append(entry['player_id'])

    current_ratings = {}
    for id in player_ids:
        player_data = lookup_player(config, player_id=id)
        current_ratings[id] = player_data['player_elo']

    for player in entries:
        overall_change = 0
        for i in range(7):
            if player['calculated_score'] > i:
                # win condition
                for opp in grouped[i]:
                    change = calculate_elo(current_ratings[player['player_id']], current_ratings[opp['player_id']], 1)
                    overall_change += change
            elif player['calculated_score'] == i:
                # draw condition
                for opp in grouped[i]:
                    if player == opp:
                        # Player is included in this, do not calculate against themselves
                        continue
                    change = calculate_elo(current_ratings[player['player_id']], current_ratings[opp['player_id']], 0.5)
                    overall_change += change
            else:
                # loss condition
                for opp in grouped[i]:
                    change = calculate_elo(current_ratings[player['player_id']], current_ratings[opp['player_id']], 0)
                    overall_change += change
        score_data = {
            'elo': current_ratings[player['player_id']] + overall_change,
            'elo_delta': overall_change
        }
        players_data = {
            'player_elo': current_ratings[player['player_id']] + overall_change,
            'elo_delta': overall_change
        }
        update_score_entry(config, player['id'], score_data)
        update_player_entry(config, player['player_id'], players_data)
        
def blame(uuid: str, puzzle: int):
    """
    Legacy ELO Calculation
    Translate rankings into 1-1 matches between each player, then sum the elo change
    """
    query_params = f"WHERE puzzle = {puzzle} AND hard_mode = 1"
    entries = get_entries(config, query_params)
    entries = sorted(entries, key=lambda x: x['calculated_score'], reverse=True)
    
    player_ids = []
    grouped = {i: [] for i in range(7)}  # Initialize keys 0 through 6
    for entry in entries:
        score = entry.get('calculated_score')
        grouped[score].append(entry)
        player_ids.append(entry['player_id'])

    current_ratings = {}
    player_info = {}
    target_id = 0
    for id in player_ids:
        player_data = lookup_player(config, player_id=id)
        if player_data['player_uuid'] == uuid:
            target_id = player_data['player_id']
        player_info[id] = player_data
        current_ratings[id] = player_data['player_elo']

    output_string = ""
    for player in entries:
        if player['player_id'] == target_id:
            output_string = f"{output_string}Analysis of {player_info[player['player_id']]['player_name']}'s Performance in Wordle #{puzzle}:"
            output_string = f"{output_string}\n\n{player_info[player['player_id']]['player_name']} started with an ELO of {round(current_ratings[player['player_id']], 3)}\n"
            overall_change = 0
            for i in range(7):
                if player['calculated_score'] > i:
                    # win condition
                    for opp in grouped[i]:
                        change = calculate_elo(current_ratings[player['player_id']], current_ratings[opp['player_id']], 1)
                        overall_change += change
                        output_string = f"{output_string}\n\tWon against {player_info[opp['player_id']]['player_name']}. ELO Change: {round(change, 3)}"
                elif player['calculated_score'] == i:
                    # draw condition
                    for opp in grouped[i]:
                        if player == opp:
                            # Player is included in this, do not calculate against themselves
                            continue
                        change = calculate_elo(current_ratings[player['player_id']], current_ratings[opp['player_id']], 0.5)
                        overall_change += change
                        output_string = f"{output_string}\n\tTied against {player_info[opp['player_id']]['player_name']}. ELO Change: {round(change, 3)}"
                else:
                    # loss condition
                    for opp in grouped[i]:
                        change = calculate_elo(current_ratings[player['player_id']], current_ratings[opp['player_id']], 0)
                        overall_change += change
                        output_string = f"{output_string}\n\tLost against {player_info[opp['player_id']]['player_name']}. ELO Change: {round(change, 3)}"

            output_string = f"{output_string}\n\nIn total {player_info[player['player_id']]['player_name']}'s ELO changed by {round(overall_change, 3)}, bringing their new ELO rating to: {round(current_ratings[player['player_id']] + overall_change, 3)}"
    if output_string == "":
        output_string = f"{uuid} did not play Wordle #{puzzle}!"
    return output_string

def get_daily_ranks(puzzle: int):
    # query_string = f"SELECT player_name, hard_mode, calculated_score FROM scores WHERE puzzle = {puzzle}"
    # data = get_entries(query_string)
    query_params = f"WHERE puzzle = {puzzle}"
    data = get_entries(config, query_params)
    for result in data:
        result['hard_mode'] = 'Y' if result['hard_mode'] == 1 else 'N'
        player_data = lookup_player(config, player_id=result['player_id'])
        result['player_name'] = player_data['player_name']
    sorted_players = sorted(data, key=lambda x: x['calculated_score'], reverse=True)
    player_chart = '| Player | Hard Mode | Ranking |\n| --- | --- | --- |'
    i = 0
    last_score = 0
    for player in sorted_players:
        if player['calculated_score'] == last_score:
            pass
        else:
            last_score = player['calculated_score']
            i += 1
        player['rank'] = i
        player_chart = f"{player_chart}\n| {player['player_name']} | {player['hard_mode']} | {player['rank']} |"

    output = {
        'raw_data': sorted_players,
        'md_chart': player_chart,
    }
    return output

def get_daily_report(today: date):
    """
    Provide a ranking of all players in order of their OpenSkill rank
    """
    puzzle = get_wordle_puzzle(today - timedelta(days=1))
    players = defaultdict(list)
    player_stats = {}
    player_data = get_all_players(config)

    query_params = f"WHERE puzzle = {puzzle}"
    entries = get_entries(config, query_params)
    for entry in entries:
        players[entry['player_id']].append(entry)
    
    players = dict(players)
    for player, scores in players.items():
        player_stats[player] = {}

        for score in scores:
            player_stats[player]['end_elo'] = round(score['elo'], 3)
            player_stats[player]['elo_change'] = round(score['elo_delta'], 3)

            player_stats[player]['end_ord'] = round(score['ordinal'], 5)
            player_stats[player]['ord_change'] = round(score['ordinal_delta'], 5)
    
    # sort player_stats by end ordinal
    sorted_keys = sorted(player_stats, key=lambda k: player_stats[k]['end_ord'], reverse=True)
    raw_sorted_player_stats = {}
    for key in sorted_keys:
        raw_sorted_player_stats[key] = player_stats[key]

    sorted_player_stats = {}
    for k, v in raw_sorted_player_stats.items():
        player_name = match_player_name(player_data, player_id=k)
        sorted_player_stats[player_name] = v

    output = {
        'sorted_player_stats': sorted_player_stats
    }
    return output

def get_weekly_report(end_date: date):
    """
    Provide a weekly report of all players showing:
        - Beginning ELO
        - End ELO
        - Average score
    """
    start_date = end_date - timedelta(days=7)
    end = get_wordle_puzzle(end_date)
    start = get_wordle_puzzle(start_date)
    players = defaultdict(list)
    player_stats = {}
    player_data = get_all_players(config)

    query_params = f"WHERE puzzle >= {start} and puzzle <= {end}"
    entries = get_entries(config, query_params)
    for entry in entries:
        players[entry['player_id']].append(entry)
    
    players = dict(players)
    for player, scores in players.items():
        player_stats[player] = {}

        all_scores = []
        earliest = end + 1
        latest = 0
        for score in scores:
            all_scores.append(score['score'])
            if score['puzzle'] > latest:
                player_stats[player]['end_elo'] = round(score['elo'], 3)
                player_stats[player]['end_ord'] = round(model.rating(mu=score['mu'], sigma=score['sigma']).ordinal(), 5)
                latest = score['puzzle']
            if score['puzzle'] < earliest:
                player_stats[player]['start_elo'] = round(score['elo'], 3)
                player_stats[player]['start_ord'] = round(model.rating(mu=score['mu'], sigma=score['sigma']).ordinal(), 5)
                earliest = score['puzzle']
        player_stats[player]['average_score'] = round(sum(all_scores) / len(all_scores), 1)
        player_stats[player]['elo_change'] = round(player_stats[player]['end_elo'] - player_stats[player]['start_elo'], 3)
        player_stats[player]['ord_change'] = round(player_stats[player]['end_ord'] - player_stats[player]['start_ord'], 3)
    
    # sort player_stats by end ordinal
    sorted_keys = sorted(player_stats, key=lambda k: player_stats[k]['end_ord'], reverse=True)
    raw_sorted_player_stats = {}
    for key in sorted_keys:
        raw_sorted_player_stats[key] = player_stats[key]

    sorted_player_stats = {}
    for k, v in raw_sorted_player_stats.items():
        player_name = match_player_name(player_data, player_id=k)
        sorted_player_stats[player_name] = v

    output = {
        'sorted_player_stats': sorted_player_stats
    }
    return output

def elo_decay():
    """
    Degrade a players ELO on an unplayed day.
    Since players are not allowed to play on weekends or days off, this is going to require more logic on the client side
    """
    pass

def is_puzzle_valid(puzzle: int):
    current_puzzle = get_wordle_puzzle(datetime.now(tz_eastern).date())
    if current_puzzle <= puzzle:
        return True
    else:
        return False

# ---
# FastAPI Security Functions
# ---

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(USERS, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ---
# API Configuration
# ---

@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(USERS, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@app.post('/register')
async def register(player_data: Player, current_user: Annotated[User, Depends(get_current_active_user)]):
    player_data = dict(player_data)
    data = lookup_player(config, player_uuid=player_data['player_uuid'])
    if data == {}:
        player = model.rating(name='test')
        player_data.update({
            'player_elo': 400,
            'player_sigma': player.sigma,
            'player_mu': player.mu,
            'player_ord': player.ordinal(),
            'elo_delta': 0,
            'ord_delta': 0,
            'mu_delta': 0,
            'sigma_delta': 0,
        })
        register_player(config, player_data)
        return player_data
    else:
        return {'status': 409}
        

@app.post('/update-registration')
async def update_registration(player_data: Player, current_user: Annotated[User, Depends(get_current_active_user)]):
    players = get_all_players(config)
    player_data = dict(player_data)
    for player in players:
        if player['player_uuid'] == player_data['player_uuid']:
            data = {
                'player_name': player_data['player_name']
            }
            update_player_entry(config, player['player_id'], data)
            return lookup_player(config, player_uuid=player_data['player_uuid'])

@app.post('/add-score/')
async def add_score(score: Score, current_user: Annotated[User, Depends(get_current_active_user)]):
    """
    Add player score to DB
    """
    player_data = lookup_player(config, score.uuid)
    if player_data == {}:
        return {
            'status': 404,
            'msg': f"{score.uuid} is not registered for Wordle!"
        }
    data = parse_score(score.score)
    score_data = get_entries(config, f"WHERE player_id = {player_data['player_id']} AND puzzle = {data['puzzle']}")
    if score_data == []:
        data['player_id'] = player_data['player_id']
        data ['raw_score'] = score.score
        if data['hard_mode'] == 0:
            data['elo'] = player_data['player_elo']
            data['mu'] = player_data['player_mu']
            data['sigma'] = player_data['player_sigma']
            data['ordinal'] = player_data['player_ord']
            data['elo_delta'] = player_data['elo_delta']
            data['ordinal_delta'] = player_data['ord_delta']
        if is_puzzle_valid(data['puzzle']):
            add_entry(config, data)
            data['player_name'] = player_data['player_name']
            return data
        else:
            return {
                'status': 409,
                'msg': f"The window for submitting Wordle #{data['puzzle']} is closed!"
            }
    else:
        return {
            'status': 409,
            'msg': f"{player_data['player_name']} already submitted Wordle #{data['puzzle']}"
        }

@app.post('/backfill-scores')
async def backfill_scores(backfill_data: BackfillData, current_user: Annotated[User, Depends(get_current_active_user)]):
    openskill = False
    elo = False

    match backfill_data.calc_type:
        case 'openskill':
            openskill = True
        case 'elo':
            elo = True
        case 'all':
            openskill = True
            elo = True
        case _:
            return {
                'status': 400,
                'msg': 'Field calc_type should be either openskill, elo, or all'
            }
    
    for puzzle in range(backfill_data.start_puzzle, backfill_data.end_puzzle + 1):
        if check_players(puzzle, puzzle, True):
            if openskill:
                calculate_openskill(puzzle)
            if elo:
                calculate_match_elo(puzzle)
        else:
            pass
    
    return {
        'status': 200,
        'msg': 'Backfill completed sucessfully.'
    }

@app.get('/score/{uuid}')
async def get_score(uuid, current_user: Annotated[User, Depends(get_current_active_user)], puzzle: int = get_wordle_puzzle(datetime.now(tz_eastern).date())):
    player_data = lookup_player(config, uuid)

    if player_data == {}:
        return {
            'status': 404,
            'msg': f"{uuid} is not registered for Wordle!"
        }

    query_params = f"WHERE puzzle = {puzzle} AND player_id = {player_data['player_id']}"
    score_data = get_entries(config, query_params)
    if score_data == []:
        return {'status': 404, 'msg': f'{player_data['player_name']} did not played today :('}
    else:
        score_data = score_data[0]
        score_data['player_information'] = player_data
        return score_data

@app.get('/blame/{uuid}')
async def blame_score(uuid, current_user: Annotated[User, Depends(get_current_active_user)], puzzle: int = get_wordle_puzzle(datetime.now(tz_eastern).date()) - 1):
    msg = blame(uuid, puzzle)
    return {'msg': msg}

@app.get('/calculate-daily/')
async def calculate_daily(current_user: Annotated[User, Depends(get_current_active_user)], puzzle_date: date = datetime.now(tz_eastern).date()):
    puzzle = get_wordle_puzzle(puzzle_date)
    if check_players(puzzle, puzzle, True):
        calculate_openskill(puzzle)
        calculate_match_elo(puzzle)
    else:
        pass
    return {'status': 200}

@app.get('/daily-ranks/')
async def daily_ranks(current_user: Annotated[User, Depends(get_current_active_user)], report_date: date = datetime.now(tz_eastern).date()):
    """
    Provide a ranking of all players based on their performance (rank only, hard mode independent) in a given puzzle
    """
    puzzle = get_wordle_puzzle(report_date)
    if check_players(puzzle, puzzle, False):
        output = get_daily_ranks(puzzle)
    else:
        output = {'status': 404, 'msg': 'Nobody played today :('}
    return output

@app.get('/daily-summary/')
async def daily_summary(current_user: Annotated[User, Depends(get_current_active_user)], report_date: date = datetime.now(tz_eastern).date()):
    puzzle = get_wordle_puzzle(report_date - timedelta(days=1))
    if check_players(puzzle, puzzle, False):
        data = get_daily_report(report_date)
    else:
        data = {'status': 404, 'msg': 'Nobody played today :('}
    return data

@app.get('/weekly-summary/')
async def weekly_summary(current_user: Annotated[User, Depends(get_current_active_user)], end_date: date = datetime.now(tz_eastern).date()):
    start_date = end_date - timedelta(days=7)
    end = get_wordle_puzzle(end_date)
    start = get_wordle_puzzle(start_date)

    if check_players(start, end, False):
        data = get_weekly_report(end_date)
    else:
        data = {'status': 404, 'msg': 'Nobody played today :('}
    return jsonable_encoder(data)

@app.get('/leaderboard')
async def leaderboard(current_user: Annotated[User, Depends(get_current_active_user)]):
    player_data = get_all_players(config)
    sorted_player_data = sorted(player_data, key=lambda player: player['player_ord'], reverse=True)
    return sorted_player_data