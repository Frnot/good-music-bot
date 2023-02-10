import logging
log = logging.getLogger(__name__)


def to_lower(input):
    return input.lower()

<<<<<<< HEAD
async def send_confirmation(ctx, delete_after=0):
    """Confirm command (and delete command <dalete_after> seconds later)"""
=======
async def send_confirmation(ctx, delete_after=10):
    """Confirm command (and delete command 10 seconds later)"""
>>>>>>> dfd2c4a497fbb9c6e81a9fb1734946b2edf24f6d
    await ctx.message.add_reaction("🫡")
    if delete_after:
        await ctx.message.delete(delay=delete_after)
