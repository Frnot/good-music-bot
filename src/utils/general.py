import logging
log = logging.getLogger(__name__)


def to_lower(input):
    return input.lower()

def sec_to_minsec(seconds):
    """Converts integer seconds to a string <minutes>:<seconds>:"""
    m,s = divmod(seconds, 60)
    return f"{m}:{s:02}"

async def send_confirmation(ctx, delete_after=0):
    """Confirm command (and delete command <dalete_after> seconds later)"""
    await ctx.message.add_reaction("🫡")
    if delete_after:
        await ctx.message.delete(delay=delete_after)
