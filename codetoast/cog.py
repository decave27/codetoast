# -*- coding: utf-8 -*-

from discord.ext import commands

from codetoast.cogs.main import Main
from codetoast.cogs.filesystem import FileSystem

__all__ = (
    "CodeToast",
    "CodeToast_COMMANDS",
    "setup",
)
CodeToast_COMMANDS = (Main, FileSystem)


class CodeToast(*CodeToast_COMMANDS):
    """
    CodeToast cog
    """


def setup(bot: commands.Bot):
    bot.add_cog(CodeToast(bot=bot))
