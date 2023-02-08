import logging
log = logging.getLogger(__name__)


def to_lower(input):
    return input.lower()

async def send_confirmation(ctx):
    # Confirm command (and delete command 30 seconds later)
    await ctx.message.add_reaction("🫡")
    await ctx.message.delete(delay=30)
