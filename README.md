# Competitive Ranked Wordle

[![Docker Pulls](https://img.shields.io/docker/pulls/jivandabeast/competitive-ranked-wordle)](https://hub.docker.com/r/jivandabeast/competitive-ranked-wordle)
[![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/jivandabeast/competitive-ranked-wordle)](https://hub.docker.com/r/jivandabeast/competitive-ranked-wordle)
[![GitHub last commit](https://img.shields.io/github/last-commit/jivandabeast/Competitive-Ranked-Wordle)](https://github.com/jivandabeast/Competitive-Ranked-Wordle/commits/master)
[![GitHub](https://img.shields.io/github/license/jivandabeast/Competitive-Ranked-Wordle)](https://github.com/jivandabeast/Competitive-Ranked-Wordle/blob/master/LICENSE)

Backend API based server for handling competitive multiplayer games of Wordle.

## Features

- Handles score parsing
- Generates a daily ranking of players (hard mode non-exclusive)
- Calculates multiplayer ELO and OpenSkill ratings for each player (hard mode exclusive)
- Generates a daily report of ELO and OpenSkill ratings (sorted by OpenSkill ordinal)
- Generates a weekly report of ELO and OpenSkill ratings (sorted by OpenSkill ordinal)
- Ability to "blame" your ELO changes on other players (provides a detailed output of matchups against other players and ELO lost/gained)

## Setup

### Docker

The docker image is hosted on Docker Hub.

- **Docker Hub Repository:** [`https://hub.docker.com/repository/docker/jivandabeast/competitive-ranked-wordle/general`](https://hub.docker.com/repository/docker/jivandabeast/competitive-ranked-wordle/general)

1. **Pull the Docker image**

   ```bash
   docker pull jivandabeast/competitive-ranked-wordle:latest
   ```
   *(replace `:latest` with a specific version if needed)*

2. **Create a folder for the resources & create required files**

   ```bash
   mkdir -p /docker/competitive-ranked-wordle/Output
   cd /docker/competitive-ranked-wordle
   wget https://raw.githubusercontent.com/jivandabeast/Competitive-Ranked-Wordle/master/config.sample.yml
   touch wordle.db
   touch Output/out.log
   mv config.sample.yml config.yml
   ```

3. **Edit `config.yml`**, following the prompts in the file.

4. **Execute the docker image**

   ```bash
   docker run -d --name competitive-ranked-wordle -v /docker/competitive-ranked-wordle:/data -e CONFIG_FILE=/data/config.yml -p 8080:80 jivandabeast/competitive-ranked-wordle:latest
   ```

5. **Open the Web-UI** being hosted on Port 8080.
