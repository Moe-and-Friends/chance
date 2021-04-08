import asyncio
import datetime
import discord
import random

from collections import defaultdict
from config import settings
from discord.ext.tasks import loop
from functools import partial

TIME_INTERVALS = (
    ('days', 3600),
    ('hours', 60),
    ('minutes', 1),
)

CHANCES = defaultdict(lambda: lambda: 0)

CHANCES_INTERVALS = sorted(settings.get("CHANCES_INTERVALS"))
CHANCES_INTERVALS_START_AT_ZERO = settings.get("CHANCES_INTERVALS_ALL_START_AT_ZERO")

# Load the Russian Roulette chances
# Use a partial function because lambdas are for loop scoped.


def get_mute_range(*args):
    try:
        return random.randint(args[0], args[1])
    except:
        return random.randint(0, args[0])


for i in range(0, len(CHANCES_INTERVALS)):
    # Nested to handle the zero case
    if i == 0:
        CHANCES[0] = partial(get_mute_range, CHANCES_INTERVALS[0])
    else:
        if CHANCES_INTERVALS_START_AT_ZERO:
            CHANCES[i] = partial(get_mute_range, CHANCES_INTERVALS[i])
        else:
            CHANCES[i] = partial(get_mute_range, CHANCES_INTERVALS[i-1], CHANCES_INTERVALS[i])

# Store this here because DD will cache calls otherwise
CHANCES_SELECT_RANGE = len(CHANCES) * settings.get('CHANCES_INVERTED_MULTIPLIER')

# Emojis that will trigger the bot to fire.
TRIGGERS = set(settings.get("TRIGGERS", []))
# Roles that are excluded from receiving LETHAL_ROLE_IDSs
COMRADE_ROLE_IDS = set(settings.get("COMRADE_ROLE_IDS", []))
# Roles added to users when they get unlucky with Russian roulette.
LETHAL_ROLE_IDS = set(settings.get("LETHAL_ROLE_IDS", []))

def display_time(minutes, granularity=2):
    """
    Converts the minutes we have into an English string to display to users.
    """
    result = []
    for name, count in TIME_INTERVALS:
        value = minutes // count
        if value:
            minutes -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    start, _, end = ', '.join(result[:granularity]).rpartition(',')
    return start + " and" + end if start else end


# Enable the members intents so we can remove the mute role once the timeout gives up.
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

muted_users = set()  # For tracking when users get muted.


@ loop(seconds=5)
async def countdown_to_unmute():
    await client.wait_until_ready()

    now = datetime.datetime.now()

    for entry in [x for x in muted_users]:
        if now > entry[1]:  # If the current time is greater than the predetermined ban time.

            guild = client.get_guild(entry[0].guild.id)
            author = guild.get_member(entry[0].author.id)
            roles = [guild.get_role(rid) for rid in LETHAL_ROLE_IDS]

            print("time has passed for user {}".format(entry[0].author.id))
            for role in roles:
                await author.remove_roles(role, atomic=True)
            print("Removed role?")
            muted_users.remove(entry)

import pprint

@ client.event
async def on_message(message):

    # Ignore messages sent by other bots, including oneself.
    if message.author.bot:
        return

    if not message.channel.id in settings.get("DISCORD_GUILD_IDS"):
        return

    if any(emoji in message.content for emoji in TRIGGERS):

        chances_key = random.randint(0, CHANCES_SELECT_RANGE)
        effect_time = CHANCES[chances_key]()

        exclude_roles = [message.guild.get_role(sid) for sid in COMRADE_ROLE_IDS]
        author_roles = message.author.roles
        roles_to_add = [message.guild.get_role(rid) for rid in LETHAL_ROLE_IDS]

        is_user_safe = any(role in author_roles for role in exclude_roles)

        if effect_time > 0:

            # Get the roles for comparison

            # Don't mute any excluded roles (yes this is inefficient)
            if is_user_safe:

                await message.reply(settings.get('NANA_COMRADE_LETHAL_MESSAGE').format(
                    time=display_time(effect_time, 3)
                ))

            else:

                # Wait for the role add to go through BEFORE calculating remove time.
                for role in roles_to_add:
                    await message.author.add_roles(role, atomic=True)

                now = datetime.datetime.now()
                uneffect_time = now + datetime.timedelta(seconds=5)
                muted_users.add((message, uneffect_time))

                await message.reply(settings.get('NANA_CAPITALIST_LETHAL_MESSAGE').format(
                    time=display_time(effect_time, 3)
                ))

        else:

            if is_user_safe:
                await message.reply(settings.get('NANA_COMRADE_SAFE_MESSAGE'))
            else:
                await message.reply(settings.get('NANA_CAPITALIST_LETHAL_MESSAGE'))


countdown_to_unmute.start()
client.run(settings.get("DISCORD_TOKEN"))
