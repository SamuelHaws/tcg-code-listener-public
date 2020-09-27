'''
##############################################################################################################

This script starts up a Discord bot client, makes GET requests periodically to a TCG code sharing 
subreddit, and sends messages with relevant post details (including codes) to a Discord text channel.

Author: Samuel Haws (https://github.com/SamuelHaws)

Relevant Documentation:
    discord.py: https://discordpy.readthedocs.io/en/latest/index.html
    Python Coroutines and ayncio: https://docs.python.org/3/library/asyncio-task.html
    APScheduler AsyncIOScheduler: https://apscheduler.readthedocs.io/en/stable/modules/schedulers/asyncio.html

##############################################################################################################
'''

import aiohttp
import asyncio
import json
import os
import discord
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime

# Fetch environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CODES_CHANNEL = os.getenv('DISCORD_CODES_CHANNEL')
REDDIT_JOB_NAME = os.getenv('REDDIT_JOB_NAME')
REDDIT_JOB_INTERVAL = os.getenv('REDDIT_JOB_INTERVAL')

# Start Discord bot Client
client = discord.Client()

async def get_json(http_client, url):
    async with http_client.get(url) as response:
        assert response.status == 200
        return await response.read()

async def get_discord_channel():
    try:
        # Attempt to fetch Channel object from cache
        channel_got = client.get_channel(DISCORD_CODES_CHANNEL)
        # If Channel not yet cached, fetch with API call
        if not channel_got:
            print(f'Channel ID {DISCORD_CODES_CHANNEL} not found in cache, will await fetch...')
            channel_got = await client.fetch_channel(DISCORD_CODES_CHANNEL)
            return channel_got
    except Exception as err:
        print(f'Error occurred while getting or fetching Discord channel: {err}')

# Fetches new posts from Reddit and sends to Discord
async def get_new_code_posts_job():
    try:
        async with aiohttp.ClientSession() as http_session:
            # Load IDs of already fetched posts (to check against and prevent duplicates)
            with open('fetched_posts.txt') as json_file:
                existing_post_ids = json.load(json_file)
            # Send request to Reddit to fetch posts
            res = await get_json(http_session, 'http://www.reddit.com/r/PokemonTcgCodes/new.json?limit=3')
            # All posts from response (oldest first)
            fetched_posts = [post['data'] for post in json.loads(res.decode('utf-8'))['data']['children']][::-1]
            for post in fetched_posts:
                # If post hasn't already been added (sent as a message)
                if post['id'] not in existing_post_ids:
                    print(f"Post with ID: {post['id']} not found in stored IDs. Sending Discord message...")
                    # Construct Discord message
                    divider = '--------------------------------------------------------------------------------------\n'
                    msg = f"{divider}**NEW REDDIT POST**\n\nTitle: {post['title']}\n\nPermalink: https://www.reddit.com{post['permalink']}\n\nURL: {post['url']}\n\nText: {post['selftext']}\n\nScore: {post['score']}\n\nNumber of Comments: {post['num_comments']}\n\nTimestamp: {datetime.fromtimestamp(post['created_utc'])}"
                    # Send message to appropriate channel
                    discord_channel = await get_discord_channel()
                    await discord_channel.send(msg)
                    # Track post as already sent
                    existing_post_ids.append(post['id'])
                else:
                    print(f"Post with ID: {post['id']} already fetched before (found in stored IDs).")

            # Update JSON of already fetched posts with newly fetched posts
            with open('fetched_posts.txt', 'w') as outfile:
                json.dump(existing_post_ids, outfile, indent=4)
        await http_session.close()
            
    except AssertionError as err:
        print(f'AssertionError occurred on response status from Reddit GET: {err}')
    except Exception as err:
        print(f'Error occured during Reddit post fetch or message sending: {err}')

# Initialize and start async job scheduler
scheduler = AsyncIOScheduler()
scheduler.start()

# On connect to Discord and confirmed Client ready status, add job(s) to scheduler to fetch codes periodically and post to Discord
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    print(f'Client is ready.')
    try:
        print('Removing existing jobs...')
        scheduler.remove_job(REDDIT_JOB_NAME)
    except JobLookupError:
        print(f'Job \'{DISCORD_CODES_CHANNEL}\' not found for removal.')
    print(f'Adding \'{REDDIT_JOB_NAME}\' to scheduler...')
    scheduler.add_job(get_new_code_posts_job, 'interval', seconds=15, id=f'{DISCORD_CODES_CHANNEL}')
    print(f'\'{REDDIT_JOB_NAME}\' should be added. Running job...')

client.run(DISCORD_TOKEN)




