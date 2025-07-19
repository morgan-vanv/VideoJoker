from .games import Games
from videojoker import VideoJoker

async def setup(bot: VideoJoker):
    await bot.add_cog(Games(bot))
