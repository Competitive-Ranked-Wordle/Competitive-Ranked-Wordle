"""
Competitive Ranked Wordle MariaDB Database Handler

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


import mariadb


class MariaDBHandler:
    def __init__(self, config):
        self.config = config

    def connect_db(self):
        conn = mariadb.connect(
            user=self.config['mariadb']['user'],
            password=self.config['mariadb']['password'],
            host=self.config['mariadb']['host'],
            port=self.config['mariadb']['port'],
            database=self.config['mariadb']['database'],
        )
        cur = conn.cursor()
        return conn, cur

    def create_wordle_db(self):
        try:
            conn, cur = self.connect_db()
            cur.execute("CREATE TABLE IF NOT EXISTS `players` (`player_name` text NOT NULL, `player_mu` float NOT NULL, `player_sigma` float NOT NULL, `player_ord` float DEFAULT NULL, `elo_delta` double DEFAULT NULL, `ord_delta` double DEFAULT NULL, `mu_delta` double DEFAULT NULL, `sigma_delta` double DEFAULT NULL, `player_id` int(11) NOT NULL AUTO_INCREMENT, `player_platform` text NOT NULL, `player_uuid` text NOT NULL, `player_elo` float NOT NULL DEFAULT 400, `formula_points` float DEFAULT NULL, `formula_delta` float DEFAULT NULL, `avg_top_three` float DEFAULT NULL, PRIMARY KEY (`player_id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;")
            cur.execute("CREATE TABLE IF NOT EXISTS `scores` (`id` int(11) NOT NULL AUTO_INCREMENT, `player_id` int(11) DEFAULT NULL, `puzzle` int(11) DEFAULT NULL, `raw_score` text DEFAULT NULL, `score` int(11) DEFAULT NULL, `calculated_score` int(11) DEFAULT NULL, `hard_mode` int(11) DEFAULT NULL, `elo` double DEFAULT NULL, `mu` double DEFAULT NULL, `sigma` double DEFAULT NULL, `ordinal` double DEFAULT NULL, `elo_delta` double DEFAULT NULL, `ordinal_delta` double DEFAULT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;")
            cur.execute("CREATE TABLE IF NOT EXISTS `player_formula_history` (`id` int(11) NOT NULL AUTO_INCREMENT, `player_id` int(11) NOT NULL, `formula_points` float DEFAULT NULL, `formula_delta` float DEFAULT NULL, `avg_top_three` float DEFAULT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(e)
            return False

    def update_score_entry(self, id: int, data: dict):
        conn, cur = self.connect_db()

        new_fields = ""
        i = 1
        for k, v in data.items():
            if i == len(data):
                if (isinstance(v, int) or isinstance(v, float)):
                    new_fields = f"{new_fields} {k} = {v}"
                else:
                    new_fields = f"{new_fields} {k} = '{v}'"
            else:
                if (isinstance(v, int) or isinstance(v, float)):
                    new_fields = f"{new_fields} {k} = {v},"
                else:
                    new_fields = f"{new_fields} {k} = '{v}',"
            i += 1

        query_string = f"UPDATE scores SET{new_fields} WHERE id = {id}"
        cur.execute(query_string)

        conn.commit()
        conn.close()

    def update_player_entry(self, player_id: int, data: dict):
        conn, cur = self.connect_db()

        new_fields = ""
        i = 1
        for k, v in data.items():
            if i == len(data):
                if (isinstance(v, int) or isinstance(v, float)):
                    new_fields = f"{new_fields} {k} = {v}"
                else:
                    new_fields = f"{new_fields} {k} = '{v}'"
            else:
                if (isinstance(v, int) or isinstance(v, float)):
                    new_fields = f"{new_fields} {k} = {v},"
                else:
                    new_fields = f"{new_fields} {k} = '{v}',"
            i += 1

        query_string = f"UPDATE players SET{new_fields} WHERE player_id = {player_id}"
        cur.execute(query_string)

        conn.commit()
        conn.close()

    def add_entry(self, data: dict):
        conn, cur = self.connect_db()

        cols = ""
        vals = ""
        i = 1
        for k, v in data.items():
            if i == len(data):
                if (isinstance(v, int) or isinstance(v, float)):
                    cols = f"{cols} {k}"
                    vals = f"{vals} {v}"
                else:
                    cols = f"{cols} {k}"
                    vals = f"{vals} '{v}'"
            else:
                if (isinstance(v, int) or isinstance(v, float)):
                    cols = f"{cols} {k},"
                    vals = f"{vals} {v},"
                else:
                    cols = f"{cols} {k},"
                    vals = f"{vals} '{v}',"
            i += 1

        query_string = f"INSERT INTO scores ({cols}) VALUES ({vals})"
        cur.execute(query_string)

        conn.commit()
        conn.close()

    def register_player(self, player_data: dict):
        conn, cur = self.connect_db()

        cols = ""
        vals = ""
        i = 1
        for k, v in player_data.items():
            if i == len(player_data):
                if (isinstance(v, int) or isinstance(v, float)):
                    cols = f"{cols} {k}"
                    vals = f"{vals} {v}"
                else:
                    cols = f"{cols} {k}"
                    vals = f"{vals} '{v}'"
            else:
                if (isinstance(v, int) or isinstance(v, float)):
                    cols = f"{cols} {k},"
                    vals = f"{vals} {v},"
                else:
                    cols = f"{cols} {k},"
                    vals = f"{vals} '{v}',"
            i += 1

        query_string = f"INSERT INTO players ({cols}) VALUES ({vals})"
        cur.execute(query_string)

        conn.commit()
        conn.close()

    def add_formula_history_entry(self, player_id: int, formula_points: float, formula_delta: float, avg_top_three: float):
        """
        Append a snapshot of a player's formula scoring state to player_formula_history.
        Called once per player per weekly formula calculation to preserve week-over-week trends.
        """
        conn, cur = self.connect_db()

        query_string = (
            f"INSERT INTO player_formula_history (player_id, formula_points, formula_delta, avg_top_three) "
            f"VALUES ({player_id}, {formula_points}, {formula_delta}, {avg_top_three})"
        )
        cur.execute(query_string)

        conn.commit()
        conn.close()

    def get_entries(self, query_params: str):
        conn, cur = self.connect_db()

        cols = [
            'id',
            'player_id',
            'puzzle',
            'raw_score',
            'score',
            'calculated_score',
            'hard_mode',
            'elo',
            'mu',
            'sigma',
            'ordinal',
            'elo_delta',
            'ordinal_delta'
        ]

        query_string = f"SELECT "
        i = 1
        for col in cols:
            query_add = ""
            if i == len(cols):
                query_add = f"{col} "
            else:
                query_add = f"{col}, "
            query_string = f"{query_string}{query_add}"
            i += 1
        query_string = f"{query_string}FROM scores {query_params}"

        cur.execute(query_string)
        scores_raw = cur.fetchall()

        score_data = []
        for row in scores_raw:
            i = 0
            row_dict = {}
            for cell in row:
                row_dict[cols[i]] = cell
                i += 1
            score_data.append(row_dict)

        conn.close()
        return score_data

    def lookup_player(self, player_uuid: str = False, player_id: int = False):
        conn, cur = self.connect_db()

        cols = [
            'player_id',
            'player_uuid',
            'player_name',
            'player_platform',
            'player_mu',
            'player_sigma',
            'player_ord',
            'player_elo',
            'elo_delta',
            'ord_delta',
            'mu_delta',
            'sigma_delta',
            'formula_points',
            'formula_delta',
            'avg_top_three'
        ]

        query_string = f"SELECT "
        i = 1
        for col in cols:
            query_add = ""
            if i == len(cols):
                query_add = f"{col} "
            else:
                query_add = f"{col}, "
            query_string = f"{query_string}{query_add}"
            i += 1

        if player_uuid:
            query_string = f"{query_string}FROM players WHERE player_uuid = '{player_uuid}'"
        elif player_id:
            query_string = f"{query_string}FROM players WHERE player_id = '{player_id}'"
        cur.execute(query_string)
        player_raw = cur.fetchall()
        if player_raw == []:
            return {}
        else:
            player_raw = player_raw[0]

        i = 0
        player_data = {}
        for cell in player_raw:
            player_data[cols[i]] = cell
            i += 1

        conn.close()
        return player_data

    def get_all_players(self):
        conn, cur = self.connect_db()

        cols = [
            'player_id',
            'player_uuid',
            'player_name',
            'player_platform',
            'player_mu',
            'player_sigma',
            'player_ord',
            'player_elo',
            'elo_delta',
            'ord_delta',
            'mu_delta',
            'sigma_delta',
            'formula_points',
            'formula_delta',
            'avg_top_three'
        ]

        query_string = f"SELECT "
        i = 1
        for col in cols:
            query_add = ""
            if i == len(cols):
                query_add = f"{col} "
            else:
                query_add = f"{col}, "
            query_string = f"{query_string}{query_add}"
            i += 1

        query_string = f"{query_string}FROM players"
        cur.execute(query_string)
        player_raw = cur.fetchall()

        players = []
        for player in player_raw:
            player_data = {}
            i = 0
            for cell in player:
                player_data[cols[i]] = cell
                i += 1
            players.append(player_data)

        conn.close()
        return players
