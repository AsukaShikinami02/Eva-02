import json
import discord
from discord.ext import commands


intents = discord.Intents.all()
# Create the bot instance
bot = commands.Bot(command_prefix="E!", intents=intents)



# Your bot data (use a persistent data structure like JSON or database to store it)
data = {}

# Function to save data to a JSON file
def save_data():
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

# Function to load data from a JSON file
def load_data():
    global data
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}  # If the file doesn't exist, start with empty data

# Function to update the bot's status with the current fronting member
async def update_bot_status(user_id):
    if user_id in data and data[user_id]["proxy_enabled"] and data[user_id]["current_member"]:
        current_member = data[user_id]["current_member"]["name"]
        status = f"Fronting as {current_member}"
        await bot.change_presence(activity=discord.Game(name=status))
    else:
        # Default status when no member is fronting
        await bot.change_presence(activity=discord.Game(name="Not fronting"))

# Command to allow users to upload the system.json file
@bot.event
async def on_message(message):
    if message.author == bot.user:  # Prevent the bot from responding to itself
        return

    user_id = str(message.author.id)

    # Check if user data exists and proxy is enabled
    if user_id in data and data[user_id]["proxy_enabled"] and data[user_id]["current_member"]:
        current_member = data[user_id]["current_member"]

        # Get the color for the member if it's set, otherwise default to blue
        member_color = current_member.get('color', "#0000FF")  # Default to blue if no color is set
        embed_color = discord.Color(int(member_color.replace('#', ''), 16))  # Convert hex color to Discord color

        # Create embed with the member's avatar and their color
        embed = discord.Embed(description=message.content, color=embed_color)
        embed.set_author(name=current_member['name'], icon_url=current_member['avatar_url'])

        # If there are attachments, forward them as the current member
        if message.attachments:
            for attachment in message.attachments:
                file = await attachment.to_file()
                await message.channel.send(
                    content=f"{current_member['name']} sent an attachment:",
                    embed=embed,  # Include the embed with the member's name, avatar, and color
                    file=file  # Send the file object (after awaiting)
                )
        else:
            # If no attachments, send the embed with just the text content
            await message.channel.send(embed=embed)

        # Delete the original message after sending the embed
        await message.delete()

        # Allow the bot to process commands even if the message is proxied.
        await bot.process_commands(message)  # Allow the bot to process commands after sending the proxied message
    else:
        # If proxy is disabled or no member is selected, respond as the bot itself
        await bot.process_commands(message)  # Let the bot process commands

# Command to switch to a specific member (proxying as that member)
@bot.command()
async def switch_member(ctx, member_name: str):
    user_id = str(ctx.author.id)

    if user_id not in data or not data[user_id]["members"]:
        await ctx.send("No members found in your data.")
        return

    # Find the member by name
    member = next((m for m in data[user_id]["members"] if m["name"].lower() == member_name.lower()), None)
    if not member:
        await ctx.send(f"Member `{member_name}` not found.")
        return

    # Set the current member
    data[user_id]["current_member"] = member
    save_data()

    await ctx.send(f"Switched to member: {member['name']}")

    # Update the bot's status with the current fronting member
    await update_bot_status(user_id)

# Command to toggle proxying on/off
@bot.command()
async def toggle_proxy(ctx):
    user_id = str(ctx.author.id)

    if user_id not in data:
        data[user_id] = {"members": [], "current_member": None, "proxy_enabled": True}

    # Toggle the proxy_enabled flag
    data[user_id]["proxy_enabled"] = not data[user_id]["proxy_enabled"]
    save_data()

    status = "enabled" if data[user_id]["proxy_enabled"] else "disabled"
    await ctx.send(f"Proxying is now {status}.")

    # Update the bot's status based on the new proxy status
    await update_bot_status(user_id)

# Command to delete a system member
@bot.command()
async def delete_member(ctx, member_name: str):
    user_id = str(ctx.author.id)

    if user_id not in data or not data[user_id]["members"]:
        await ctx.send("No members found in your data.")
        return

    member = next((m for m in data[user_id]["members"] if m["name"].lower() == member_name.lower()), None)
    if not member:
        await ctx.send(f"Member `{member_name}` not found.")
        return

    data[user_id]["members"].remove(member)
    save_data()

    await ctx.send(f"Successfully deleted member: {member_name}")

    # If the deleted member is the current fronting member, clear the status
    if data[user_id]["current_member"] and data[user_id]["current_member"]["name"].lower() == member_name.lower():
        data[user_id]["current_member"] = None
        save_data()

    # Update the bot's status
    await update_bot_status(user_id)

# Command to add a new member with an avatar and color
@bot.command()
async def add_member(ctx, member_name: str, avatar_url: str = None, color: str = None):
    user_id = str(ctx.author.id)

    if user_id not in data:
        data[user_id] = {"members": [], "current_member": None, "proxy_enabled": True}

    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]  # Use the first uploaded attachment as the avatar
        avatar_url = attachment.url

    # Default to blue color if none is provided
    if not color:
        color = "#0000FF"

    # Store member data with the avatar and color
    data[user_id]["members"].append({"name": member_name, "avatar_url": avatar_url, "color": color})
    save_data()

    await ctx.send(f"Successfully added member: {member_name} with avatar: {avatar_url} and color: {color}")

# Command to allow users to upload the system.json file
@bot.command()
async def import_members(ctx):
    # Accept file upload for system.json
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            if attachment.filename == "system.json":
                file_content = await attachment.read()
                try:
                    system_data = json.loads(file_content)
                    user_id = str(ctx.author.id)

                    # Initialize the user's data if not present
                    if user_id not in data:
                        data[user_id] = {"members": [], "current_member": None, "proxy_enabled": True}

                    # Import members from system.json
                    members = system_data.get('members', [])
                    updated_count = 0
                    new_count = 0

                    for member in members:
                        member_name = member['name']
                        avatar_url = member.get('avatar_url', None)
                        color = member.get('color', "#0000FF")  # Default to blue if no color is set

                        # Check if the member already exists
                        existing_member = next((m for m in data[user_id]["members"] if m["name"].lower() == member_name.lower()), None)

                        if existing_member:
                            # Update existing member's data
                            existing_member['avatar_url'] = avatar_url
                            existing_member['color'] = color
                            updated_count += 1
                        else:
                            # Add new member if not found
                            data[user_id]["members"].append({"name": member_name, "avatar_url": avatar_url, "color": color})
                            new_count += 1

                    # Save the data to data.json after importing
                    save_data()

                    await ctx.send(f"Successfully imported {new_count} new members and updated {updated_count} members.")
                except json.JSONDecodeError:
                    await ctx.send("Invalid system.json file. Please ensure it's correctly formatted.")
                    
@bot.command()
async def list_members(ctx):
    user_id = str(ctx.author.id)

    # Check if the user has members stored
    if user_id not in data or not data[user_id]["members"]:
        await ctx.send("You don't have any members in your system.")
        return

    members = data[user_id]["members"]

    # Iterate over members and create an individual embed for each member
    for member in members:
        member_name = member['name']
        avatar_url = member.get('avatar_url', None)  # If there's no avatar, set it to None
        color = member.get('color', '#0000FF')  # Default color if not set

        # Convert color from hex to a Discord-compatible color
        embed_color = discord.Color(int(color.strip("#"), 16))

        # Create an embed for each member
        embed = discord.Embed(
            title=member_name, 
            description=f"**Name:** {member_name}\n**Color:** {color}", 
            color=embed_color
        )

        # If the member has an avatar, set it as the thumbnail
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        # Send the embed for each member
        await ctx.send(embed=embed)
# Start the bot with your token
load_data()  # Load the saved data before running the bot
# 


bot.run('your_token_here')