# -*- coding: utf-8 -*-

from discord.ext import commands

__all__ = (
    "CodeToast",
    "CodeToast_COMMANDS",
    "setup",
)
CodeToast_COMMANDS = ()


class CodeToast(*CodeToast_COMMANDS):
    """
    CodeToast cog
    """


def setup(bot: commands.Bot):
    bot.add_cog(CodeToast(bot=bot))
