import logging
log = logging.getLogger(__name__)


def to_lower(input):
    return input.lower()

async def send_confirmation(ctx, delete_after=10):
    """Confirm command (and delete command 10 seconds later)"""
    await ctx.message.add_reaction("🫡")
    if delete_after:
        await ctx.message.delete(delay=delete_after)
