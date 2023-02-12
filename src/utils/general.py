import logging

log = logging.getLogger(__name__)


def to_lower(input):
    return input.lower()

def sec_to_minsec(seconds):
    """Converts integer seconds to a string <minutes>:<seconds>:"""
    m,s = divmod(seconds, 60)
    return f"{m}:{s:02}"

def timestr_to_secs(timestr):
    timearr = timestr.split(":")
    timearr.reverse()
    return sum([a*b for a,b in zip([1,60,3600], map(int,timearr))])

async def send_confirmation(ctx, delete_after=0):
    """Confirm command (and delete command <dalete_after> seconds later)"""
    await ctx.message.add_reaction("🫡")
    if delete_after:
        await ctx.message.delete(delay=delete_after)
